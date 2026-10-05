"""One bounded CV job per process. No network or subprocess execution allowed."""
import base64,hashlib,json,os,resource,sys,tempfile
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_DATASETS_OFFLINE='1',TOKENIZERS_PARALLELISM='false',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',YOLO_OFFLINE='true')
resource.setrlimit(resource.RLIMIT_CPU,(180,180))
resource.setrlimit(resource.RLIMIT_AS,(int(os.getenv('SENTINEL_ML_MEMORY_MB','8192'))*1024*1024,)*2)
resource.setrlimit(resource.RLIMIT_NOFILE,(128,128))
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
def boundary(event,args):
    if event in ('socket.connect','socket.connect_ex','subprocess.Popen','os.system'):raise PermissionError('CV sandbox denies network and subprocess execution')
sys.addaudithook(boundary)

def run(body):
    from .registry import spec,digest,public,inventory
    operation=body['operation']
    if operation=='identity':return digest(spec(body['model_id']),verify=False)
    if operation=='registry':return {'models':[public(m) for m in inventory()]}
    from .adapters import Adapter,image,inspection
    temporary=tempfile.TemporaryDirectory(prefix='sentinel-model-')
    def load_adapter(model,filename):
        m=model['inline_model'];kind=m.get('adapter','').lower()
        if kind not in ('onnx','pytorch','torchscript'):raise ValueError('Unsupported uploaded model format')
        raw=base64.b64decode(m['bytes_b64'],validate=True)
        if len(raw)>8*1024*1024:raise ValueError('Uploaded model exceeds workspace limit')
        p=os.path.join(temporary.name,filename+'.'+kind)
        with open(p,'wb') as stream:stream.write(raw)
        definition={k:m.get(k) for k in ('adapter','architecture','task','classes','input_size','sha256')}
        definition['_ephemeral_path']=p;return Adapter(definition)
    adapter=load_adapter(body,'candidate') if body.get('inline_model') else Adapter(spec(body.get('model_id','dinov2-small')))
    if operation=='inspect':return inspection(adapter)
    if operation=='infer':return {'output':adapter.infer(image(body['image_b64']),body.get('classes')),'model_identity':digest(adapter.spec),
        'runtime':{'python':sys.version.split()[0],'torch':adapter.torch.__version__,'device':adapter.device,'adapter':adapter.kind,
                   'adapter_code_sha256':hashlib.sha256(open(__file__.replace('runner.py','adapters.py'),'rb').read()).hexdigest()}}
    if operation=='probes':
        from .probes import battery,strip,neural_cleanse
        images=[image(v['image_b64']) for v in body['samples'][:8]]
        reference=body.get('reference',{})
        reference_adapter=load_adapter(reference,'reference') if reference.get('inline_model') else Adapter(spec(reference.get('model_id',body.get('reference_id'))))
        result=battery(adapter,reference_adapter,images,body.get('classes'))
        result['inspection']=inspection(adapter);result['strip']=strip(adapter,images)
        result['neural_cleanse']=neural_cleanse(adapter,images) if body.get('deep_analysis') else {'available':False,'reason':'Deep reconstruction was not requested'}
        if adapter.kind in ('resnet','convnext','pytorch'):
            from .statistics import activation_checks
            vectors=[];labels=[];model=adapter.model
            layer=model.avgpool if hasattr(model,'avgpool') else model.classifier[0]
            captured=[];hook=layer.register_forward_hook(lambda _m,_i,out:captured.append(out.detach().flatten().cpu().numpy()))
            try:
                for v,im in zip(body['samples'][:8],images):
                    adapter.infer(im);vectors.append(captured.pop());labels.append(v.get('class_id',0))
            finally:hook.remove()
            result['activation_analysis']=activation_checks(vectors,labels)
        else:result['activation_analysis']={'available':False,'reason':'Penultimate classification activations are not exposed by this adapter'}
        return result
    from .statistics import dataset_analysis,shift
    samples=body.get('samples',[]);reference=body.get('reference',[])
    if not samples or len(samples)>256 or len(reference)>256:raise ValueError('Dataset worker accepts 1–256 current samples and at most 256 reference samples')
    vectors=[adapter.infer(image(v['image_b64']))['embedding'] for v in samples]
    baseline=[adapter.infer(image(v['image_b64']))['embedding'] for v in reference]
    if operation=='drift':return {'metrics':shift(baseline,vectors),'method':'DINOv2 embedding MMD / PSI / KS','confidence':None}
    if operation!='dataset':raise ValueError('Unknown CV operation')
    semantic=None
    if body.get('semantic_model_id') and body.get('classes'):
        clip=Adapter(spec(body['semantic_model_id']))
        semantic=[clip.infer(image(v['image_b64']),body['classes'])['probabilities'] for v in samples]
    result=dataset_analysis(vectors,baseline,[v.get('class_id') for v in samples],semantic)
    result['embeddings']=[{'asset_id':v['id'],'vector':e,'model_id':adapter.spec['id']} for v,e in zip(samples,vectors)]
    result['sample_ids']=[v['id'] for v in samples];result['assessed_samples']=len(samples);result['total_samples']=body.get('total_samples',len(samples))
    result['coverage']=len(samples)/max(1,result['total_samples']);result['model_identity']=digest(adapter.spec)
    return result

if __name__=='__main__':
    try:
        body=json.loads(sys.stdin.buffer.read(24*1024*1024));result=run(body)
        print('SENTINEL_RESULT:'+json.dumps({'ok':True,'result':result},allow_nan=False,separators=(',',':')))
    except Exception as exc:
        print('SENTINEL_RESULT:'+json.dumps({'ok':False,'error':str(exc)}));sys.exit(1)
