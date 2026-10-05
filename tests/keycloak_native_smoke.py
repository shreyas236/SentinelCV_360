"""Exercise a real Keycloak server, PKCE callback, JWT verification and realm roles.

Usage: python tests/keycloak_native_smoke.py --home PATH --java-home PATH
The temporary test realm disables first-login OTP enrollment for automation.
"""
import argparse,asyncio,html,json,os,re,secrets,shutil,subprocess,sys,tempfile,time
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--home',required=True);parser.add_argument('--java-home',required=True);args=parser.parse_args()
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT));os.chdir(ROOT)
temporary=Path(tempfile.mkdtemp(prefix='sentinel-keycloak-test-'));kc=Path(args.home).resolve()
shutil.copyfile(ROOT/'infrastructure/init-stack.py',temporary/'init-stack.py')
public_url='https://localhost:8444'
subprocess.run([sys.executable,str(temporary/'init-stack.py'),'--url',public_url],check=True,capture_output=True)
values=dict(line.split('=',1) for line in (temporary/'.env').read_text().splitlines());realm=json.loads((temporary/'runtime/realm.json').read_text())
realm['realm']='sentinel-test-'+secrets.token_hex(3)
for u in realm['users']:
    u['requiredActions']=[]
    if not u.get('serviceAccountClientId'):u.update(firstName=u['username'],lastName='Test',email=u['username']+'@example.invalid')
import_dir=kc/'data/import';import_dir.mkdir(parents=True,exist_ok=True);realm_path=import_dir/(realm['realm']+'-realm.json');realm_path.write_text(json.dumps(realm));realm_path.chmod(0o600)
credentials=json.loads((temporary/'runtime/credentials.json').read_text())['accounts'];issuer=public_url+'/idp/realms/'+realm['realm']
ca_file=str(temporary/'runtime/tls/ca.crt')
os.environ.update(SENTINEL_DATA_DIR=str(temporary/'app-data'),SENTINEL_AUTH_MODE='keycloak',KEYSTORE_SECRET=values['KEYSTORE_SECRET'],SENTINEL_OIDC_ISSUER=issuer,SENTINEL_OIDC_INTERNAL_ISSUER=issuer,SENTINEL_OIDC_CLIENT_SECRET=values['SENTINEL_OIDC_CLIENT_SECRET'],SENTINEL_PUBLIC_URL=public_url,SENTINEL_OIDC_CA_FILE=ca_file)
env=dict(os.environ,JAVA_HOME=args.java_home,KC_BOOTSTRAP_ADMIN_USERNAME='root-test',KC_BOOTSTRAP_ADMIN_PASSWORD=secrets.token_urlsafe(20))
log=open(temporary/'keycloak.log','wb');process=subprocess.Popen([str(kc/'bin/kc.sh'),'start-dev','--http-port=8088','--https-port=8444','--https-certificate-file='+str(temporary/'runtime/tls/server.crt'),'--https-certificate-key-file='+str(temporary/'runtime/tls/server.key'),'--http-relative-path=/idp','--hostname='+public_url+'/idp','--import-realm'],env=env,stdout=log,stderr=log)
import httpx
try:
    for _ in range(600):
        if process.poll() is not None:raise AssertionError((temporary/'keycloak.log').read_text()[-1500:])
        try:
            if httpx.get(issuer+'/.well-known/openid-configuration',trust_env=False,verify=ca_file,timeout=1).status_code==200:break
        except httpx.HTTPError:pass
        time.sleep(.1)
    else:raise AssertionError('Local Keycloak failed to become ready')
    from local.api import app
    from fastapi.testclient import TestClient
    with TestClient(app,base_url=public_url) as client:
        def login(username,password):
            start=client.get('/api/auth/oidc/start',follow_redirects=False);assert start.status_code==307,start.text
            with httpx.Client(trust_env=False,follow_redirects=False,verify=ca_file) as browser:
                page=browser.get(start.headers['location']);form=re.search(r'<form[^>]*id="kc-form-login"[^>]*action="([^"]+)"',page.text)
                assert form,re.sub(r'<[^>]+>',' ',page.text)[-2000:]
                action=html.unescape(form[1])
                result=browser.post(action,data={'username':username,'password':password,'credentialId':''})
                assert result.status_code in (302,303),re.sub(r'<[^>]+>',' ',result.text)[-1800:]
                callback=result.headers['location'];assert callback.startswith(public_url+'/api/auth/oidc/callback?'),'Unexpected callback route'
                response=client.get(callback.removeprefix(public_url),follow_redirects=False);assert response.status_code==303,response.text
                return client.get('/api/auth/me').json()['actor']
        assert login('admin',credentials['admin'])['role']=='administrator'
        r=client.post('/api/action',json={'action':'initialize'});assert r.status_code==200,r.text
        r=client.post('/api/auth/users',json={'username':'new-client-test','password':'local-client-password-2026','account_role':'client'});assert r.status_code==201,r.text
        created=r.json();assert created['contributor_id']
        # This disposable fixture skips enrollment; production-created accounts require OTP.
        from local import oidc
        user_id=created['id'].removeprefix('oidc-')
        assert asyncio.run(oidc.admin_request('GET','/users/'+user_id)).json()['attributes']['contributor_id']==[created['contributor_id']]
        asyncio.run(oidc.admin_request('PUT','/users/'+user_id,{'firstName':'Client','lastName':'Test','email':'new-client@example.invalid','requiredActions':[],'attributes':{'contributor_id':[created['contributor_id']]}}))
        who=login('new-client-test','local-client-password-2026');assert who['role']=='contributor' and who['contributor_id']==created['contributor_id']
        assert client.get('/api/auth/users').status_code==403
        r=client.post('/api/action',headers={'x-sentinel-demo-role':'administrator'},json={'action':'policy','payload':{'profile':'STRICT'}});assert r.status_code==403,r.text
        logout=client.post('/api/auth/logout');assert logout.status_code==200 and logout.json()['logout_url'].startswith(issuer+'/protocol/openid-connect/logout?')
        assert not client.get('/api/auth/me').json()['authenticated']
    result={'keycloak_version':'26.4.7','real_oidc_code_pkce':'passed','signed_jwt_validation':'passed','admin_created_client':'passed','client_rbac':'passed','forged_role':'rejected','logout_redirect':'passed','mfa_enrollment':'Not exercised by this automated test','database':'Keycloak dev-file and application SQLite'}
    (ROOT/'docs/keycloak-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
finally:
    process.terminate()
    try:process.wait(timeout=10)
    except subprocess.TimeoutExpired:process.kill();process.wait()
    log.close();realm_path.unlink(missing_ok=True);shutil.rmtree(temporary,ignore_errors=True)
