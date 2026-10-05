"""Local FastAPI boundary: fixed-role sessions and a private shared analysis process."""
import asyncio,hashlib,hmac,json,os,secrets,sqlite3,subprocess,time
from contextlib import asynccontextmanager
from pathlib import Path
import httpx
from fastapi import FastAPI,Request
from fastapi.responses import JSONResponse,Response,FileResponse,RedirectResponse
from fastapi.staticfiles import StaticFiles
from .setup import provision, ACCOUNT_ROLES
from .auth_store import connect as authconnect
from . import oidc
ROOT=Path(__file__).resolve().parent.parent
DATA=Path(os.getenv('SENTINEL_DATA_DIR',str(ROOT/'local-data'))).resolve()
ENGINE_PORT=int(os.getenv('SENTINEL_ENGINE_PORT','8766'))
TOKEN=secrets.token_urlsafe(32)
SERVICE_TOKEN=os.getenv('SENTINEL_SERVICE_TOKEN','')
users={};process=None

def authdb():return authconnect(DATA)

def actor(request):
    token=request.cookies.get('sentinel_session','')
    if not token:return None
    with authdb() as conn:row=conn.execute('SELECT username,expires,identity_json FROM login_sessions WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
    if not row or row[1]<time.time():return None
    return {k:v for k,v in json.loads(row[2]).items() if not k.startswith('_')} if row[2] else users.get(row[0])

async def authaudit(event,user,details=None):
    try:
        async with httpx.AsyncClient(timeout=10,trust_env=False) as client:
            await client.post(f'http://127.0.0.1:{ENGINE_PORT}/api/action',headers={'x-internal-token':TOKEN,'x-sentinel-actor':user.get('id','unknown'),'x-sentinel-role':user.get('role','auditor')},json={'action':'auth_audit','payload':{'event':event,'details':details or {}}})
    except httpx.HTTPError:pass

@asynccontextmanager
async def lifespan(app):
    global users,process
    os.chdir(ROOT)
    if os.getenv('SENTINEL_AUTH_MODE')=='keycloak':
        DATA.mkdir(parents=True,exist_ok=True);config={'keystore_secret':os.environ['KEYSTORE_SECRET']};users={}
    else:
        _,credentials=provision(DATA)
        for name,password in credentials:print(f'New local account {name}: {password}',flush=True)
        users=json.loads((DATA/'users.json').read_text())
        config=json.loads((DATA/'config.json').read_text())
    env=dict(os.environ,KEYSTORE_SECRET=config['keystore_secret'],SENTINEL_INTERNAL_TOKEN=TOKEN,SENTINEL_DATA_DIR=str(DATA),SENTINEL_ENGINE_PORT=str(ENGINE_PORT))
    process=subprocess.Popen(['node','local/server.ts'],cwd=ROOT,env=env)
    try:
        for _ in range(100):
            if process.poll() is not None:raise RuntimeError('Analysis engine stopped during startup.')
            try:
                async with httpx.AsyncClient(trust_env=False,timeout=2) as c:
                    r=await c.get(f'http://127.0.0.1:{ENGINE_PORT}/api/state',headers={'x-internal-token':TOKEN,'x-sentinel-actor':'local-auditor','x-sentinel-role':'auditor'})
                    if r.status_code==200:break
            except httpx.HTTPError:pass
            await asyncio.sleep(.1)
        else:raise RuntimeError('Analysis engine did not become ready.')
        yield
    finally:
        process.terminate()
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:process.kill()

app=FastAPI(title='SentinelCV 360 local API',version='1.1.0',lifespan=lifespan,docs_url='/api/docs',openapi_url='/api/openapi.json')
@app.middleware('http')
async def boundary(request,call_next):
    if request.method=='POST':
        origin=request.headers.get('origin')
        if origin and origin not in {str(request.base_url).rstrip('/'),'http://127.0.0.1:5173','http://localhost:5173'}:return JSONResponse({'error':'Origin rejected'},403)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff';response.headers['Cache-Control']='no-store'
    return response
@app.post('/api/auth/login')
async def login(request:Request):
    if os.getenv('SENTINEL_AUTH_MODE')=='keycloak':return JSONResponse({'error':'Use the local Keycloak sign-in button.'},409)
    try:body=await request.json()
    except ValueError:return JSONResponse({'error':'Invalid login request'},400)
    username=str(body.get('username',''))[:128];password=str(body.get('password',''))[:1024];user=users.get(username)
    with authdb() as conn:attempt=conn.execute('SELECT failures,locked_until FROM login_attempts WHERE username=?',(username,)).fetchone()
    if attempt and attempt[1]>time.time():return JSONResponse({'error':'Account locked temporarily. Retry after 15 minutes.'},429)
    if not user or (body.get('account_role') and body['account_role']!=user.get('account_role',next((k for k,v in ACCOUNT_ROLES.items() if v==user['role']),user['role']))) or not hmac.compare_digest(hashlib.scrypt(password.encode(),salt=bytes.fromhex(user['salt']),n=16384,r=8,p=1).hex(),user['password_hash']):
        with authdb() as conn:
            n=(attempt[0] if attempt and attempt[1]<=time.time() else 0)+1
            conn.execute('INSERT INTO login_attempts VALUES(?,?,?) ON CONFLICT(username) DO UPDATE SET failures=excluded.failures,locked_until=excluded.locked_until',(username,n,time.time()+900 if n>=5 else 0))
        await authaudit('LOGIN_FAILED',user or {'id':'unknown','role':'auditor'})
        return JSONResponse({'error':'Invalid username or password'},401)
    token=secrets.token_urlsafe(32)
    with authdb() as conn:
        conn.execute('DELETE FROM login_attempts WHERE username=?',(username,));conn.execute('INSERT INTO login_sessions(token_hash,username,expires) VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),username,time.time()+3600))
    await authaudit('LOGIN',user)
    response=JSONResponse({'role':user['role'],'user_id':user['id'],'account_role':user.get('account_role')})
    response.set_cookie('sentinel_session',token,httponly=True,samesite='strict',secure=request.url.scheme=='https',max_age=3600)
    return response
@app.post('/api/auth/logout')
async def logout(request:Request):
    user=actor(request)
    with authdb() as conn:
        row=conn.execute('DELETE FROM login_sessions WHERE token_hash=? RETURNING identity_json',(hashlib.sha256(request.cookies.get('sentinel_session','').encode()).hexdigest(),)).fetchone()
    if user:await authaudit('LOGOUT',user)
    body={'ok':True}
    if row and row[0] and os.getenv('SENTINEL_AUTH_MODE')=='keycloak':
        from urllib.parse import urlencode
        cfg=oidc.settings();hint=json.loads(row[0]).get('_oidc_id_token')
        params={'client_id':cfg['client_id'],'post_logout_redirect_uri':os.environ['SENTINEL_PUBLIC_URL'].rstrip('/')+'/'}
        if hint:params['id_token_hint']=hint
        body['logout_url']=cfg['issuer']+'/protocol/openid-connect/logout?'+urlencode(params)
    response=JSONResponse(body);response.delete_cookie('sentinel_session');return response
@app.get('/api/auth/me')
async def me(request:Request):
    user=actor(request)
    return {'mode':'LOCAL OFFLINE PROFILE','authenticated':bool(user),'setup_required':False,
            'auth_mode':os.getenv('SENTINEL_AUTH_MODE','password'),'actor':{k:user.get(k) for k in ('id','role','contributor_id','username','account_role')} if user else None}

@app.get('/api/auth/oidc/start')
async def oidc_start():
    if os.getenv('SENTINEL_AUTH_MODE')!='keycloak':return JSONResponse({'error':'Keycloak is not configured'},503)
    cfg=oidc.settings();state=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(64);nonce=secrets.token_urlsafe(32)
    with authdb() as conn:
        conn.execute('DELETE FROM oidc_states WHERE expires<=?',(time.time(),))
        conn.execute('INSERT INTO oidc_states VALUES(?,?,?,?)',(hashlib.sha256(state.encode()).hexdigest(),verifier,nonce,time.time()+300))
    from urllib.parse import urlencode
    response=RedirectResponse(cfg['issuer']+'/protocol/openid-connect/auth?'+urlencode({'client_id':cfg['client_id'],'redirect_uri':cfg['redirect'],'response_type':'code','scope':'openid profile','state':state,'nonce':nonce,'code_challenge':oidc.challenge(verifier),'code_challenge_method':'S256'}))
    response.set_cookie('sentinel_oidc_state',state,httponly=True,samesite='lax',secure=cfg['redirect'].startswith('https:'),max_age=300)
    return response

@app.get('/api/auth/oidc/callback')
async def oidc_callback(request:Request):
    state=request.query_params.get('state','');code=request.query_params.get('code','')
    if not state or not code or len(code)>4096 or not hmac.compare_digest(state,request.cookies.get('sentinel_oidc_state','')):return JSONResponse({'error':'Identity callback state rejected'},400)
    with authdb() as conn:
        # DELETE RETURNING consumes state exactly once in both database profiles.
        row=conn.execute('DELETE FROM oidc_states WHERE state_hash=? AND expires>? RETURNING verifier,nonce',(hashlib.sha256(state.encode()).hexdigest(),time.time())).fetchone()
    if not row:return JSONResponse({'error':'Identity login expired or replayed'},400)
    try:user,tokens,claims=await oidc.exchange(code,row[0],row[1])
    except Exception:return JSONResponse({'error':'Identity token verification failed'},401)
    if user['role']=='contributor' and not user.get('contributor_id'):return JSONResponse({'error':'Client contributor identity is not provisioned'},403)
    token=secrets.token_urlsafe(32)
    with authdb() as conn:conn.execute('INSERT INTO login_sessions VALUES(?,?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),user['username'],min(claims['exp'],time.time()+3600),json.dumps({**user,'_oidc_id_token':tokens['id_token']}),tokens['access_token']))
    await authaudit('LOGIN',user)
    response=RedirectResponse('/',status_code=303);response.delete_cookie('sentinel_oidc_state')
    response.set_cookie('sentinel_session',token,httponly=True,samesite='strict',secure=oidc.settings()['redirect'].startswith('https:'),max_age=max(1,int(min(claims['exp']-time.time(),3600))))
    return response

@app.get('/api/auth/users')
async def list_users(request:Request):
    user=actor(request)
    if not user or user['role']!='administrator':return JSONResponse({'error':'Administrator access required'},403)
    if os.getenv('SENTINEL_AUTH_MODE')=='keycloak':
        try:
            rows=(await oidc.admin_request('GET','/users?max=100')).json()
            result=[]
            for row in rows:
                roles=(await oidc.admin_request('GET','/users/'+row['id']+'/role-mappings/realm')).json()
                matched=[oidc.ROLE_MAP[r['name']] for r in roles if r['name'] in oidc.ROLE_MAP]
                if len(matched)==1:result.append({'id':row['id'],'username':row['username'],'role':matched[0][0],'account_role':matched[0][1]})
            return {'users':result}
        except httpx.HTTPError:return JSONResponse({'error':'Local identity service unavailable'},503)
    return {'users':[{k:u.get(k) for k in ('id','username','role','account_role','contributor_id')} for u in users.values()]}

@app.post('/api/auth/users')
async def create_user(request:Request):
    user=actor(request)
    if not user or user['role']!='administrator':return JSONResponse({'error':'Administrator access required'},403)
    body=await request.json();name=str(body.get('username','')).strip().lower();password=str(body.get('password',''));account_role=str(body.get('account_role',''))
    import re
    if not re.fullmatch(r'[a-z0-9][a-z0-9._-]{2,63}',name) or not 12<=len(password)<=256 or account_role not in ACCOUNT_ROLES:return JSONResponse({'error':'Use a valid username, a password of at least 12 characters and a supported role.'},400)
    if name in users:return JSONResponse({'error':'Username already exists'},409)
    contributor_id=None
    if account_role=='client':
        async with httpx.AsyncClient(trust_env=False,timeout=10) as c:
            r=await c.post(f'http://127.0.0.1:{ENGINE_PORT}/api/action',headers={'x-internal-token':TOKEN,'x-sentinel-actor':user['id'],'x-sentinel-role':'administrator'},json={'action':'register_contributor','payload':{'name':name,'organization':body.get('organization','')}})
            if r.status_code!=200:return JSONResponse({'error':'Contributor registration failed'},503)
            contributor_id=r.json()['id']
    if os.getenv('SENTINEL_AUTH_MODE')=='keycloak':
        try:result=await oidc.create_user(name,password,account_role,contributor_id)
        except httpx.HTTPError:return JSONResponse({'error':'Local identity service rejected account creation'},503)
    else:
        salt=secrets.token_hex(16);result={'id':'local-'+secrets.token_hex(8),'username':name,'role':ACCOUNT_ROLES[account_role],'account_role':account_role,'contributor_id':contributor_id}
        users[name]={**result,'salt':salt,'password_hash':hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()}
        temporary=DATA/'users.new';temporary.write_text(json.dumps(users,indent=2));os.chmod(temporary,0o600);temporary.replace(DATA/'users.json')
    await authaudit('ACCOUNT_PROVISIONED',user,{'account_id':result['id'],'account_role':account_role})
    return JSONResponse(result,201)

@app.get('/health')
async def health():return {'status':'ok','mode':'local','analysis_process_alive':process is not None and process.poll() is None}
@app.get('/metrics')
async def metrics(request:Request):
    user=actor(request)
    supplied=request.headers.get('authorization','').removeprefix('Bearer ')
    if not user and len(SERVICE_TOKEN)>=32 and hmac.compare_digest(supplied,SERVICE_TOKEN):user={'id':'monitoring-collector','role':'auditor'}
    if not user:return JSONResponse({'error':'Authentication required'},401)
    async with httpx.AsyncClient(trust_env=False) as c:
        r=await c.get(f'http://127.0.0.1:{ENGINE_PORT}/api/state',headers={'x-internal-token':TOKEN,'x-sentinel-actor':user['id'],'x-sentinel-role':user['role']})
        data=r.json()
    lines=['sentinel_'+k+' '+str(v) for k,v in data.get('counts',{}).items()]
    lines.append('sentinel_audit_events '+str(data.get('audit_count',0)))
    try:
        import psutil
        lines.extend(['sentinel_cpu_percent '+str(psutil.cpu_percent()),'sentinel_memory_percent '+str(psutil.virtual_memory().percent),'sentinel_disk_percent '+str(psutil.disk_usage(str(DATA)).percent)])
    except ImportError:pass
    return Response('\n'.join(lines)+'\n',media_type='text/plain')
@app.post('/internal/task')
async def internal_task(request:Request):
    if len(SERVICE_TOKEN)<32 or not hmac.compare_digest(request.headers.get('x-service-token',''),SERVICE_TOKEN):return JSONResponse({'error':'Service authentication required'},403)
    body=await request.json();user=body.get('actor',{})
    if body.get('action') not in ('scan_dataset','scan_model','benchmark','report','drift'):return JSONResponse({'error':'Task not allowed'},400)
    async with httpx.AsyncClient(trust_env=False,timeout=240) as c:
        r=await c.post(f'http://127.0.0.1:{ENGINE_PORT}/api/action',headers={'x-internal-token':TOKEN,'x-sentinel-actor':user.get('id',''),'x-sentinel-role':user.get('role','')},json={'action':body['action'],'payload':body.get('payload',{})})
    return Response(r.content,status_code=r.status_code,media_type='application/json')

@app.post('/api/jobs')
async def submit_job(request:Request):
    user=actor(request)
    if not user or user['role'] not in ('analyst','administrator','supervisor'):return JSONResponse({'error':'Assessment role required'},403)
    if not os.getenv('SENTINEL_REDIS_URL'):return JSONResponse({'error':'Background worker is not configured'},503)
    body=await request.json();action=body.get('action')
    if action not in ('scan_dataset','scan_model','benchmark','report','drift') or user['role']=='supervisor' and action!='report':return JSONResponse({'error':'Task not permitted for this account'},403)
    from .tasks import assessment
    import redis
    job=assessment.delay(action,body.get('payload',{}),{k:user[k] for k in ('id','role')})
    redis.Redis.from_url(os.environ['SENTINEL_REDIS_URL']).setex('sentinel:job:'+job.id+':owner',3600,user['id'])
    return JSONResponse({'job_id':job.id,'state':'PENDING'},202)

@app.get('/api/jobs/{job_id}')
async def job_status(job_id:str,request:Request):
    user=actor(request)
    if not user:return JSONResponse({'error':'Authentication required'},401)
    if not os.getenv('SENTINEL_REDIS_URL'):return JSONResponse({'error':'Background worker is not configured'},503)
    import redis
    from .tasks import celery_app
    owner=redis.Redis.from_url(os.environ['SENTINEL_REDIS_URL']).get('sentinel:job:'+job_id+':owner')
    if owner!=user['id'].encode():return JSONResponse({'error':'Job not found'},404)
    result=celery_app.AsyncResult(job_id)
    return {'job_id':job_id,'state':result.state,'result':result.result if result.successful() else None,'error':'Background assessment failed' if result.failed() else None}

@app.api_route('/api/{path:path}',methods=['GET','POST'])
async def proxy(path:str,request:Request):
    user=actor(request)
    if not user:return JSONResponse({'error':'Authentication required'},401)
    chunks=[];size=0
    async for chunk in request.stream():
        size+=len(chunk)
        if size>15*1024*1024:return JSONResponse({'error':'Request exceeds 15 MB'},413)
        chunks.append(chunk)
    body=b''.join(chunks)
    if request.method=='POST':
        try:payload=json.loads(body)
        except ValueError:return JSONResponse({'error':'Invalid JSON'},400)
        if payload.get('action')=='auth_audit':return JSONResponse({'error':'Reserved internal action'},403)
    headers={'x-internal-token':TOKEN,'x-sentinel-actor':user['id'],'x-sentinel-role':user['role'],'content-type':request.headers.get('content-type','application/json')}
    if user['contributor_id']:headers['x-sentinel-contributor']=user['contributor_id']
    try:
        async with httpx.AsyncClient(trust_env=False,timeout=180) as c:r=await c.request(request.method,f'http://127.0.0.1:{ENGINE_PORT}/api/{path}',params=request.query_params,headers=headers,content=body)
    except httpx.HTTPError:return JSONResponse({'error':'Local analysis service unavailable'},503)
    response_headers={k:v for k,v in r.headers.items() if k.lower() in ('content-type','content-disposition','cache-control')}
    return Response(r.content,status_code=r.status_code,headers=response_headers)
if (ROOT/'offline-dist').exists():
    app.mount('/assets',StaticFiles(directory=ROOT/'offline-dist/assets'),name='assets')
@app.get('/favicon.svg')
async def favicon():return FileResponse(ROOT/'public/favicon.svg',media_type='image/svg+xml')
@app.get('/')
async def index():
    if (ROOT/'offline-dist/index.html').exists():return FileResponse(ROOT/'offline-dist/index.html')
    return JSONResponse({'message':'Run npm run build:local, or use npm run dev:local on port 5173.'})
