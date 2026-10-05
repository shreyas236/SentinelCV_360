"""Exercise the actual FastAPI boundary and shared engine without external services."""
import os,tempfile,json,shutil,sys
from pathlib import Path
root=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(root));os.chdir(root)
directory=tempfile.mkdtemp(prefix='sentinel-api-test-')
os.environ['SENTINEL_DATA_DIR']=directory
for role in ('analyst','administrator','supervisor','operator','contributor','auditor'):os.environ['SENTINEL_'+role.upper()+'_PASSWORD']='test-only-password-'+role
from local.setup import provision
provision(directory)
from local.api import app
from fastapi.testclient import TestClient
try:
 with TestClient(app) as client:
    assert client.get('/api/state').status_code==401
    assert client.get('/health').json()['analysis_process_alive']
    def login(role):
        r=client.post('/api/auth/login',json={'username':role,'password':'test-only-password-'+role})
        assert r.status_code==200,r.text
    def action(action,payload=None,status=200):
        r=client.post('/api/action',json={'action':action,'payload':payload or {}})
        assert r.status_code==status,r.text
        return r.json()
    login('analyst')
    base=action('initialize')
    inference=action('run_inference',{'model_id':base['model_id'],'dataset_id':base['dataset_id']})
    assert action('verify_inference',{'asset_id':inference['id']})['valid']
    assert action('accept_inference',{'asset_id':inference['id']})['accepted']
    assert not action('replay',{'asset_id':inference['id']})['accepted']
    assert not action('tamper',{'asset_id':inference['id'],'target':'OUTPUT'})['valid']
    attack=action('attack',{'type':'TRIGGER','asset_id':base['dataset_id'],'rate':5,'seed':47321})
    scan=action('scan_dataset',{'asset_id':attack['asset']['id']})
    case=action('case_create',{'finding_id':scan['scan']['findings'][0]})
    action('case_recommend',{'case_id':case['id'],'disposition':'QUARANTINE'})
    client.post('/api/auth/logout')
    login('supervisor')
    assert action('case_approve',{'case_id':case['id']})['status']=='CLOSED'
    report=action('report',{'case_id':case['id']})
    pdf=client.get('/api/artifact/'+report['id'])
    assert pdf.content.startswith(b'%PDF')
    assert client.get('/api/state').json()['actor']['role']=='supervisor'
    client.post('/api/auth/logout');login('auditor')
    action('scan_dataset',{'asset_id':base['dataset_id']},403)
    forged=client.post('/api/action',headers={'x-sentinel-demo-role':'administrator','x-sentinel-role':'administrator'},json={'action':'policy','payload':{'profile':'STRICT'}})
    assert forged.status_code==403
    assert action('audit_verify')['valid']
    print(json.dumps({'local_api_authentication':'passed','persistent_role_enforcement':'passed','tamper_and_replay':'passed','distinct_identity_approval':'passed','signed_pdf_download':'passed'}))
finally:shutil.rmtree(directory,ignore_errors=True)
