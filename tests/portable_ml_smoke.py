"""Execute all portable task contracts and uploaded-model signed provenance."""
import base64,hashlib,io,json,os,secrets,shutil,subprocess,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT));os.chdir(ROOT)
import torch,httpx
from PIL import Image
torch.manual_seed(27641)
class Portable(torch.nn.Module):
    def __init__(self,task):super().__init__();self.task=task;self.conv=torch.nn.Conv2d(3,3,1)
    def forward(self,x):
        if self.task=='DETECTION':return torch.tensor([[[16.,32.,180.,192.,.8,1.]]])+x.sum()*0
        y=self.conv(x)
        return y if self.task=='SEGMENTATION' else y.mean(dim=(2,3))
buffer=io.BytesIO();Image.new('RGB',(224,224),(20,80,150)).save(buffer,format='PNG');encoded=base64.b64encode(buffer.getvalue()).decode()
def execute(body):
    p=subprocess.run([sys.executable,'-m','local.ml.runner'],input=json.dumps(body).encode(),capture_output=True,timeout=215)
    rows=[r for r in p.stdout.decode().splitlines() if r.startswith('SENTINEL_RESULT:')];assert rows,p.stderr.decode()[-500:]
    r=json.loads(rows[-1].split(':',1)[1]);assert r['ok'],r;return r['result']
results=[];fixture=None;directory=Path(tempfile.mkdtemp(prefix='sentinel-portable-'))
try:
    for kind in ('onnx','torchscript'):
        for task in ('CLASSIFICATION','DETECTION','SEGMENTATION','EMBEDDING'):
            model=Portable(task).eval();x=torch.randn(1,3,224,224);file=directory/(task+'.'+kind)
            if kind=='onnx':torch.onnx.export(model,x,str(file),input_names=['images'],output_names=['output'],opset_version=17,dynamo=False)
            else:torch.jit.trace(model,x).save(str(file))
            raw=file.read_bytes();inline={'adapter':kind,'task':task,'classes':['one','two','three'],'input_size':224,'sha256':hashlib.sha256(raw).hexdigest(),'bytes_b64':base64.b64encode(raw).decode()}
            out=execute({'operation':'infer','inline_model':inline,'image_b64':encoded})['output'];assert out['task']==task
            if task=='CLASSIFICATION':assert len(out['probabilities'])==3 and abs(sum(out['probabilities'])-1)<1e-5
            if task=='DETECTION':assert out['detections'][0]['bbox']==[16.,32.,180.,192.]
            if task=='SEGMENTATION':assert out['shape']==[224,224] and sum(c['pixels'] for c in out['classes'])==224*224
            if task=='EMBEDDING':assert len(out['embedding'])==3
            results.append({'format':kind,'task':task,'passed':True})
            if kind=='onnx' and task=='CLASSIFICATION':fixture=inline
    os.environ.update(SENTINEL_DATA_DIR=str(directory/'data'),SENTINEL_SERVICE_TOKEN=secrets.token_hex(32),SENTINEL_AI_URL='http://127.0.0.1:8768')
    for name in ('analyst','administrator','supervisor','operator','contributor','auditor','user','client','admin'):os.environ['SENTINEL_'+name.upper()+'_PASSWORD']='portable-test-password-'+name
    worker=subprocess.Popen([sys.executable,'-m','uvicorn','local.ml.service:app','--host','127.0.0.1','--port','8768'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                if httpx.get('http://127.0.0.1:8768/health',trust_env=False,timeout=1).status_code==200:break
            except httpx.HTTPError:pass
            time.sleep(.1)
        from local.api import app
        from fastapi.testclient import TestClient
        with TestClient(app) as client:
            assert client.post('/api/auth/login',json={'username':'admin','password':'portable-test-password-admin','account_role':'admin'}).status_code==200
            def action(name,payload=None):
                r=client.post('/api/action',json={'action':name,'payload':payload or {}});assert r.status_code==200,r.text;return r.json()
            base=action('initialize')
            uploaded=action('upload_model',{'name':'portable-classifier.onnx','format':'ONNX','task':'CLASSIFICATION','classes':fixture['classes'],'input_size':224,'bytes_b64':fixture['bytes_b64'],'dataset_id':base['dataset_id']})
            action('approve_uploaded_model',{'asset_id':uploaded['id']})
            assessed=action('scan_model',{'asset_id':uploaded['id']});assert assessed['scan']['behavior']['agreement']==1
            # ONNX has grey-box metadata, so use the standard 50% coverage policy.
            assert assessed['disposition']=='ACCEPT',assessed
            inference=action('run_inference',{'model_id':uploaded['id'],'dataset_id':base['dataset_id']})
            assert len(inference['output']['probabilities'])==3 and action('verify_inference',{'asset_id':inference['id']})['valid']
            results.append({'uploaded_onnx_approval_assessment_signed_inference':True})
    finally:worker.terminate();worker.wait(timeout=10)
    (ROOT/'docs/portable-model-validation.json').write_text(json.dumps({'results':results,'scope':'CPU fixture execution and local API; explicit tensor contracts, not arbitrary architectures'},indent=2)+'\n')
    print(json.dumps({'portable_model_tests':'passed','results':results}))
finally:shutil.rmtree(directory,ignore_errors=True)
