"""Execute installed pretrained engines, native formats and signed API provenance."""
import base64,io,json,os,secrets,subprocess,sys,tempfile,time,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT));os.chdir(ROOT)
from PIL import Image
buffer=io.BytesIO();Image.new('RGB',(224,224),(25,120,180)).save(buffer,format='PNG');encoded=base64.b64encode(buffer.getvalue()).decode()
os.environ.update(SENTINEL_MODEL_DIR=str(ROOT/'model-vault'),SENTINEL_SERVICE_TOKEN='native-test-only-service-token-2026-abcdef',SENTINEL_AI_URL='http://127.0.0.1:8768')
def runner(body):
    p=subprocess.run([sys.executable,'-m','local.ml.runner'],input=json.dumps(body).encode(),capture_output=True,timeout=215)
    lines=[l for l in p.stdout.decode().splitlines() if l.startswith('SENTINEL_RESULT:')]
    assert lines,p.stderr.decode()[-1500:]
    result=json.loads(lines[-1].split(':',1)[1]);assert result['ok'],result
    return result['result']
results=[]
for model in ('resnet18','convnext_tiny','dinov2-small','openclip-vit-b32','yolo11n','rtdetr-r18','mask2former-small'):
    r=runner({'operation':'infer','model_id':model,'image_b64':encoded,'classes':['truck','tank','person']})
    assert r['model_identity']['valid'];results.append({'model':model,'task':r['output']['task'],'passed':True})
import torch,hashlib
class Tiny(torch.nn.Module):
    def __init__(self):super().__init__();self.conv=torch.nn.Conv2d(3,3,1)
    def forward(self,x):return self.conv(x).mean(dim=(2,3))
torch.manual_seed(47321);model=Tiny().eval();tensor=torch.randn(1,3,224,224)
with tempfile.TemporaryDirectory() as temp:
    for kind in ('onnx','torchscript'):
        file=Path(temp)/('candidate.'+kind)
        if kind=='onnx':torch.onnx.export(model,tensor,str(file),input_names=['images'],output_names=['logits'],opset_version=17,dynamo=False)
        else:torch.jit.trace(model,tensor).save(str(file))
        raw=file.read_bytes();inline={'adapter':kind,'task':'CLASSIFICATION','classes':['one','two','three'],'input_size':224,'sha256':hashlib.sha256(raw).hexdigest(),'bytes_b64':base64.b64encode(raw).decode()}
        r=runner({'operation':'infer','inline_model':inline,'image_b64':encoded});assert r['output']['task']=='CLASSIFICATION'
        results.append({'model':kind,'task':'CLASSIFICATION','passed':True})
directory=tempfile.mkdtemp(prefix='sentinel-native-api-');os.environ['SENTINEL_DATA_DIR']=directory
for username in ('analyst','administrator','supervisor','operator','contributor','auditor','user','client','admin'):os.environ['SENTINEL_'+username.upper()+'_PASSWORD']='native-test-password-'+username
worker=subprocess.Popen([sys.executable,'-m','uvicorn','local.ml.service:app','--host','127.0.0.1','--port','8768'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
import httpx
try:
    for _ in range(100):
        try:
            if httpx.get('http://127.0.0.1:8768/health',trust_env=False).status_code==200:break
        except httpx.HTTPError:pass
        time.sleep(.1)
    else:raise AssertionError('ML worker did not start')
    from local.api import app
    from fastapi.testclient import TestClient
    with TestClient(app) as client:
        assert client.post('/api/auth/login',json={'username':'admin','password':'native-test-password-admin','account_role':'admin'}).status_code==200
        def action(name,payload=None):
            r=client.post('/api/action',json={'action':name,'payload':payload or {}});assert r.status_code==200,r.text;return r.json()
        base=action('initialize');native=action('register_pretrained',{'model_id':'resnet18'});assessment=action('scan_model',{'asset_id':native['id']})
        assert assessment['disposition']=='ACCEPT',assessment
        inference=action('run_inference',{'model_id':native['id'],'dataset_id':base['dataset_id']})
        assert len(inference['output']['probabilities'])==1000
        assert inference['manifest']['model_hash']==native['sha256']
        assert action('verify_inference',{'asset_id':inference['id']})['valid']
        assert action('accept_inference',{'asset_id':inference['id']})['accepted']
        assert not action('replay',{'asset_id':inference['id']})['accepted']
        assert not action('tamper',{'asset_id':inference['id'],'target':'OUTPUT'})['valid']
        action('dataset_reference',{'asset_id':base['dataset_id']})
        scanned=action('scan_dataset',{'asset_id':base['dataset_id']})
        assert scanned['scan']['advanced']['available'],scanned['scan']['advanced']
        assert action('audit_verify')['valid']
        results.append({'native_inference_provenance':True,'replay_detected':True,'tampering_detected':True,'embedding_scan_executed':True})
finally:
    worker.terminate();worker.wait(timeout=10);shutil.rmtree(directory,ignore_errors=True)
output=ROOT/'docs/native-ml-validation.json';output.write_text(json.dumps({'results':results,'scope':'CPU execution; synthetic image inputs; not field detection accuracy or production certification'},indent=2)+'\n')
print(json.dumps({'native_ml_tests':'passed','results':results}))
