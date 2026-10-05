"""Local Keycloak authorization-code flow, PKCE and strict RS256 verification.

No discovery, JWKS or login requests are sent outside the configured local IdP.
"""
import base64, hashlib, json, os, secrets, time, ssl
from urllib.parse import urlencode
import httpx

def settings():
    base=os.environ['SENTINEL_OIDC_ISSUER'].rstrip('/')
    return {'issuer':base,'internal':os.getenv('SENTINEL_OIDC_INTERNAL_ISSUER',base).rstrip('/'),
            'client_id':os.getenv('SENTINEL_OIDC_CLIENT_ID','sentinel-api'),
            'secret':os.environ['SENTINEL_OIDC_CLIENT_SECRET'],
            'redirect':os.environ['SENTINEL_PUBLIC_URL'].rstrip('/')+'/api/auth/oidc/callback'}

def unb64(s):return base64.urlsafe_b64decode(s+'='*(-len(s)%4))
def challenge(v):return base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).decode().rstrip('=')
def tls_context():
    return ssl.create_default_context(cafile=os.environ['SENTINEL_OIDC_CA_FILE']) if os.getenv('SENTINEL_OIDC_CA_FILE') else True

def verify_token(token,jwks,issuer,audience,nonce=None):
    from cryptography.hazmat.primitives.asymmetric import rsa,padding
    from cryptography.hazmat.primitives import hashes
    if len(token)>32768:raise ValueError('Token exceeds limit')
    parts=token.split('.')
    if len(parts)!=3:raise ValueError('Invalid token')
    header=json.loads(unb64(parts[0]));payload=json.loads(unb64(parts[1]))
    if header.get('alg')!='RS256':raise ValueError('Unsupported signing algorithm')
    matches=[k for k in jwks.get('keys',[]) if k.get('kid')==header.get('kid') and k.get('kty')=='RSA' and k.get('use','sig')=='sig']
    if len(matches)!=1:raise ValueError('Unknown identity signing key')
    k=matches[0];n=int.from_bytes(unb64(k['n']),'big');e=int.from_bytes(unb64(k['e']),'big')
    if n.bit_length()<2048:raise ValueError('Identity signing key too small')
    rsa.RSAPublicNumbers(e,n).public_key().verify(unb64(parts[2]),('.'.join(parts[:2])).encode(),padding.PKCS1v15(),hashes.SHA256())
    aud=payload.get('aud',[]);aud=[aud] if isinstance(aud,str) else aud
    if payload.get('iss')!=issuer or audience not in aud or payload.get('azp',audience)!=audience:raise ValueError('Token issuer or audience mismatch')
    if not isinstance(payload.get('exp'),(int,float)) or payload['exp']<=time.time():raise ValueError('Token expired')
    if payload.get('nbf',0)>time.time()+30 or payload.get('iat',0)>time.time()+30:raise ValueError('Token clock invalid')
    if nonce is not None and not secrets.compare_digest(str(payload.get('nonce','')),nonce):raise ValueError('Token nonce mismatch')
    if not payload.get('sub'):raise ValueError('Token subject missing')
    return payload

ROLE_MAP={'sentinel-admin':('administrator','admin'),'sentinel-user':('analyst','user'),
          'sentinel-client':('contributor','client'),'sentinel-supervisor':('supervisor','supervisor'),
          'sentinel-operator':('operator','operator'),'sentinel-auditor':('auditor','auditor')}
def identity(claims):
    roles=claims.get('realm_access',{}).get('roles',[])
    selected=[(key,value) for key,value in ROLE_MAP.items() if key in roles]
    if len(selected)!=1:raise ValueError('Account must have exactly one SentinelCV role')
    _,(role,account_role)=selected[0]
    return {'id':'oidc-'+claims['sub'],'username':claims.get('preferred_username',claims['sub']),
            'role':role,'account_role':account_role,'contributor_id':claims.get('contributor_id') if role=='contributor' else None}

async def exchange(code,verifier,nonce):
    cfg=settings()
    async with httpx.AsyncClient(timeout=15,trust_env=False,verify=tls_context()) as client:
        r=await client.post(cfg['internal']+'/protocol/openid-connect/token',data={'grant_type':'authorization_code','code':code,
            'client_id':cfg['client_id'],'client_secret':cfg['secret'],'redirect_uri':cfg['redirect'],'code_verifier':verifier})
        r.raise_for_status();tokens=r.json()
        keys=await client.get(cfg['internal']+'/protocol/openid-connect/certs');keys.raise_for_status()
    # Verify the access token as well as the ID token. Roles come from the signed access token.
    verify_token(tokens['id_token'],keys.json(),cfg['issuer'],cfg['client_id'],nonce)
    claims=verify_token(tokens['access_token'],keys.json(),cfg['issuer'],cfg['client_id'])
    return identity(claims),tokens,claims

async def admin_request(method,path,json_body=None):
    cfg=settings();root=cfg['internal'].split('/realms/')[0]
    realm=cfg['internal'].split('/realms/')[1]
    async with httpx.AsyncClient(timeout=15,trust_env=False,verify=tls_context()) as client:
        token=await client.post(cfg['internal']+'/protocol/openid-connect/token',data={'grant_type':'client_credentials','client_id':cfg['client_id'],'client_secret':cfg['secret']})
        token.raise_for_status()
        r=await client.request(method,root+'/admin/realms/'+realm+path,headers={'Authorization':'Bearer '+token.json()['access_token']},json=json_body)
        r.raise_for_status();return r

async def create_user(username,password,account_role,contributor_id=None):
    reverse={v[1]:k for k,v in ROLE_MAP.items()}
    if account_role not in reverse:raise ValueError('Invalid account role')
    response=await admin_request('POST','/users',{'username':username,'enabled':True,'emailVerified':False,
        'requiredActions':['CONFIGURE_TOTP'],'attributes':{'contributor_id':[contributor_id]} if contributor_id else {},
        'credentials':[{'type':'password','value':password,'temporary':False}]})
    user_id=response.headers['location'].rsplit('/',1)[-1]
    try:
        role=(await admin_request('GET','/roles/'+reverse[account_role])).json()
        await admin_request('POST','/users/'+user_id+'/role-mappings/realm',[role])
    except Exception:
        await admin_request('DELETE','/users/'+user_id)
        raise
    return {'id':'oidc-'+user_id,'username':username,'account_role':account_role,'role':ROLE_MAP[reverse[account_role]][0],'contributor_id':contributor_id}
