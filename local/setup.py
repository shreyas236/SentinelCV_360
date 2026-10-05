"""Provision private local demo accounts. Run once, then keep the output safely."""
import hashlib,json,os,secrets
from pathlib import Path
ROLES=('analyst','administrator','supervisor','operator','contributor','auditor')
ACCOUNT_ROLES={'user':'analyst','client':'contributor','admin':'administrator','supervisor':'supervisor','operator':'operator','auditor':'auditor'}
def provision(directory=None):
    directory=Path(directory or os.getenv('SENTINEL_DATA_DIR','local-data')).resolve()
    directory.mkdir(parents=True,exist_ok=True); os.chmod(directory,0o700)
    config=directory/'config.json'; users=directory/'users.json'
    if not config.exists():
        config.write_text(json.dumps({'keystore_secret':secrets.token_hex(32)}));os.chmod(config,0o600)
    credentials=[]
    accounts=json.loads(users.read_text()) if users.exists() else {}
    for username in (*ROLES,'user','client','admin'):
        if username not in accounts:
            role=ACCOUNT_ROLES.get(username,username)
            password=os.getenv('SENTINEL_'+username.upper()+'_PASSWORD') or secrets.token_urlsafe(15)
            salt=secrets.token_hex(16)
            account_role=next((k for k,v in ACCOUNT_ROLES.items() if v==role),role)
            accounts[username]={'id':'local-'+username,'username':username,'account_role':account_role,'role':role,'salt':salt,'password_hash':hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex(),'contributor_id':'CONTRIB-DEMO' if role=='contributor' else None}
            credentials.append((username,password))
    if credentials:
        users.write_text(json.dumps(accounts,indent=2));os.chmod(users,0o600)
    return directory,credentials
if __name__=='__main__':
    directory,credentials=provision()
    if credentials:
        print('New local credentials. Store these before closing the terminal:')
        for username,password in credentials:print(username+': '+password)
    else:print('Existing local accounts preserved.')
    print('Start: uvicorn local.api:app --host 127.0.0.1 --port 8000')
