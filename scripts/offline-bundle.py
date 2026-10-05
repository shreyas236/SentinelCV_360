"""Hash and sign a prepared offline bundle; verification uses a separately pinned key."""
import argparse,hashlib,json,os
from pathlib import Path,PurePosixPath
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':')).encode()
def checksum(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def create(directory,key_path):
    directory=Path(directory).resolve();key_path=Path(key_path)
    if not key_path.exists():
        key_path.parent.mkdir(parents=True,exist_ok=True);key=Ed25519PrivateKey.generate()
        key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()));os.chmod(key_path,0o600)
    key=serialization.load_pem_private_key(key_path.read_bytes(),password=None)
    paths=sorted(p for p in directory.rglob('*') if p.is_file() and p.relative_to(directory).as_posix() not in ('bundle-manifest.json','bundle-signature.sig'))
    if any(p.is_symlink() for p in paths):raise ValueError('Offline bundle may not contain symbolic links')
    manifest={'format':'sentinel.offline-bundle.v1','files':[{ 'path':p.relative_to(directory).as_posix(),'sha256':checksum(p),'size':p.stat().st_size} for p in paths]}
    raw=canonical(manifest);(directory/'bundle-manifest.json').write_bytes(raw);(directory/'bundle-signature.sig').write_bytes(key.sign(raw))
    return key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
def verify(directory,trusted_key):
    directory=Path(directory).resolve();raw=(directory/'bundle-manifest.json').read_bytes()
    key=serialization.load_pem_public_key(Path(trusted_key).read_bytes());key.verify((directory/'bundle-signature.sig').read_bytes(),raw)
    manifest=json.loads(raw)
    if manifest.get('format')!='sentinel.offline-bundle.v1':raise ValueError('Unknown bundle format')
    expected=set()
    for row in manifest['files']:
        relative=PurePosixPath(row['path']);candidate=directory/relative
        if relative.is_absolute() or '..' in relative.parts or row['path'] in expected or any(v.is_symlink() for v in (candidate,*candidate.parents)):raise ValueError('Bundle path rejected')
        p=candidate.resolve()
        if not p.is_relative_to(directory) or not p.is_file() or p.stat().st_size!=row['size'] or checksum(p)!=row['sha256']:raise ValueError('Bundle integrity failure: '+row['path'])
        expected.add(row['path'])
    actual={p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file() and p.relative_to(directory).as_posix() not in ('bundle-manifest.json','bundle-signature.sig')}
    if expected!=actual:raise ValueError('Bundle contains unmanifested files')
    return {'valid':True,'verified_files':len(expected)}
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['create','verify']);parser.add_argument('--directory',required=True);parser.add_argument('--private-key');parser.add_argument('--trusted-key');parser.add_argument('--public-key-output');args=parser.parse_args()
    if args.action=='create':
        if not args.private_key or not args.public_key_output:parser.error('create requires a private key and public key output')
        public=create(args.directory,args.private_key);Path(args.public_key_output).parent.mkdir(parents=True,exist_ok=True);Path(args.public_key_output).write_bytes(public);print('Offline bundle signed. Transfer and pin the public key separately.')
    else:
        trusted=args.trusted_key or str(Path(__file__).resolve().parent.parent/'infrastructure/trust/build-public.pem')
        print(json.dumps(verify(args.directory,trusted)))
