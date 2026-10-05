"""Generate private LAN secrets, a local CA, and a Keycloak realm without defaults."""
import argparse,datetime,ipaddress,json,os,secrets
from pathlib import Path
from urllib.parse import urlparse
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
parser=argparse.ArgumentParser();parser.add_argument('--url',default='https://localhost:8443');args=parser.parse_args()
base=Path(__file__).resolve().parent;runtime=base/'runtime';runtime.mkdir(mode=0o700,exist_ok=True)
(runtime/'prometheus').mkdir(mode=0o700,exist_ok=True)
if (base/'.env').exists():raise SystemExit('Existing secrets preserved. Remove nothing; use the current .env file.')
values={k:secrets.token_hex(32) for k in ['SENTINEL_POSTGRES_PASSWORD','SENTINEL_MINIO_PASSWORD','SENTINEL_REDIS_PASSWORD','SENTINEL_KEYCLOAK_PASSWORD','SENTINEL_GRAFANA_PASSWORD','SENTINEL_SERVICE_TOKEN','SENTINEL_OIDC_CLIENT_SECRET','KEYSTORE_SECRET']}
values.update(SENTINEL_PUBLIC_URL=args.url.rstrip('/'),SENTINEL_UID=str(os.getuid()),SENTINEL_GID=str(os.getgid()))
def private(path,data):
    path.write_text(data);os.chmod(path,0o600)
private(base/'.env','\n'.join(k+'='+v for k,v in values.items())+'\n')
private(runtime/'service-token',values['SENTINEL_SERVICE_TOKEN'])
rolemap={'admin':'sentinel-admin','user':'sentinel-user','client':'sentinel-client','supervisor':'sentinel-supervisor','operator':'sentinel-operator','auditor':'sentinel-auditor'}
passwords={name:secrets.token_urlsafe(20) for name in rolemap}
users=[{'username':name,'enabled':True,'realmRoles':[role],'requiredActions':['CONFIGURE_TOTP'],
 'credentials':[{'type':'password','value':passwords[name],'temporary':False}],
 'attributes':{'contributor_id':['CONTRIB-DEMO']} if name=='client' else {}} for name,role in rolemap.items()]
users.append({'username':'service-account-sentinel-api','enabled':True,'serviceAccountClientId':'sentinel-api',
 'clientRoles':{'realm-management':['manage-users','view-users','query-users','view-realm']}})
profile={'attributes':[
 {'name':'username','permissions':{'view':['admin','user'],'edit':['admin','user']},'validations':{'length':{'min':3,'max':64},'username-prohibited-characters':{}}},
 *[{'name':name,'permissions':{'view':['admin','user'],'edit':['admin','user']},'validations':{'email':{}} if name=='email' else {'length':{'max':255}}} for name in ('email','firstName','lastName')],
 {'name':'contributor_id','permissions':{'view':['admin','user'],'edit':['admin']},'validations':{'length':{'max':100}},'multivalued':False}]}
realm={'realm':'sentinel','enabled':True,'registrationAllowed':False,'resetPasswordAllowed':False,'bruteForceProtected':True,
 'failureFactor':5,'waitIncrementSeconds':900,'maxFailureWaitSeconds':900,'accessTokenLifespan':300,'ssoSessionIdleTimeout':1800,
 'passwordPolicy':'length(12) and notUsername(undefined)',
 'roles':{'realm':[{'name':v} for v in rolemap.values()]},'users':users,
 'components':{'org.keycloak.userprofile.UserProfileProvider':[{'providerId':'declarative-user-profile','config':{'kc.user.profile.config':[json.dumps(profile)]}}]},
 'clients':[{'clientId':'sentinel-api','enabled':True,'publicClient':False,'secret':values['SENTINEL_OIDC_CLIENT_SECRET'],
  'standardFlowEnabled':True,'directAccessGrantsEnabled':False,'serviceAccountsEnabled':True,
  'redirectUris':[args.url.rstrip('/')+'/api/auth/oidc/callback'],'webOrigins':[args.url.rstrip('/')],
  'attributes':{'pkce.code.challenge.method':'S256','post.logout.redirect.uris':args.url.rstrip('/')+'/'},
  'protocolMappers':[{'name':'sentinel-audience','protocol':'openid-connect','protocolMapper':'oidc-audience-mapper',
    'config':{'included.client.audience':'sentinel-api','access.token.claim':'true','id.token.claim':'true'}},
    {'name':'contributor-id','protocol':'openid-connect','protocolMapper':'oidc-usermodel-attribute-mapper',
    'config':{'user.attribute':'contributor_id','claim.name':'contributor_id','jsonType.label':'String','access.token.claim':'true','id.token.claim':'true'}}]}]}
private(runtime/'realm.json',json.dumps(realm,indent=2));private(runtime/'credentials.json',json.dumps({'accounts':passwords,'keycloak_root_username':'sentinel-root','keycloak_root_password':values['SENTINEL_KEYCLOAK_PASSWORD'],'grafana_username':'admin','grafana_password':values['SENTINEL_GRAFANA_PASSWORD']},indent=2))
tls=runtime/'tls';tls.mkdir(mode=0o700,exist_ok=True)
key=rsa.generate_private_key(public_exponent=65537,key_size=3072);hostkey=rsa.generate_private_key(public_exponent=65537,key_size=3072)
name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'SentinelCV local root CA')]);now=datetime.datetime.now(datetime.timezone.utc)
ca=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(minutes=5)).not_valid_after(now+datetime.timedelta(days=1825)).add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True).sign(key,hashes.SHA256())
hostname=urlparse(args.url).hostname
try:san=x509.IPAddress(ipaddress.ip_address(hostname))
except ValueError:san=x509.DNSName(hostname)
server=x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,hostname)])).issuer_name(name).public_key(hostkey.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(minutes=5)).not_valid_after(now+datetime.timedelta(days=365)).add_extension(x509.BasicConstraints(ca=False,path_length=None),critical=True).add_extension(x509.SubjectAlternativeName([san]),critical=False).sign(key,hashes.SHA256())
for filename,value in [('ca.crt',ca.public_bytes(serialization.Encoding.PEM)),('server.crt',server.public_bytes(serialization.Encoding.PEM)),('server.key',hostkey.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())),('ca.key',key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))]:
    (tls/filename).write_bytes(value);os.chmod(tls/filename,0o600)
print('Private credentials: infrastructure/runtime/credentials.json. Trust infrastructure/runtime/tls/ca.crt on your workstation. Then run infrastructure/start-offline.sh.')
