"""Local, digest-pinned model inventory. Runtime has no downloader."""
import hashlib,json,os
from pathlib import Path

def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def root():return Path(os.getenv('SENTINEL_MODEL_DIR','model-vault')).resolve()
def path(relative):
    p=(root()/relative).resolve()
    if not p.is_relative_to(root()) or p.is_symlink():raise ValueError('Model path rejected')
    return p
def inventory():
    p=root()/'manifest.json'
    return json.loads(p.read_text()).get('models',[]) if p.exists() else []
def spec(model_id):
    found=[m for m in inventory() if m['id']==model_id]
    if len(found)!=1:raise ValueError('Model is not installed in the local vault')
    return found[0]
def digest(m,verify=True):
    if m.get('_ephemeral_path'):
        received=hashlib.sha256(Path(m['_ephemeral_path']).read_bytes()).hexdigest()
        valid=received==m['sha256']
        if verify and not valid:raise ValueError('Uploaded model digest mismatch')
        return {'sha256':received,'expected_sha256':m['sha256'],'valid':valid}
    actual=[];valid=True
    for f in sorted(m['files'],key=lambda x:x['path']):
        p=path(f['path'])
        if not p.is_file():raise ValueError('Model artifact missing: '+f['path'])
        h=hashlib.sha256()
        with p.open('rb') as stream:
            for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
        row={'path':f['path'],'sha256':h.hexdigest()};actual.append(row)
        valid=valid and row['sha256']==f['sha256']
    received=hashlib.sha256(canonical(actual).encode()).hexdigest()
    valid=valid and received==m['sha256']
    if verify and not valid:raise ValueError('Model vault identity mismatch; execution refused')
    return {'sha256':received,'expected_sha256':m['sha256'],'valid':valid}
def public(m):return {k:m.get(k) for k in ('id','name','adapter','task','sha256','classes','license','source','revision')}
