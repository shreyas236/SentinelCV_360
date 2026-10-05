"""Meaningful positive/negative checks for independently pinned offline media."""
import importlib.util,json,tempfile
from pathlib import Path
from cryptography.hazmat.primitives import serialization
ROOT=Path(__file__).resolve().parent.parent
spec=importlib.util.spec_from_file_location('bundle',ROOT/'scripts/offline-bundle.py');bundle=importlib.util.module_from_spec(spec);spec.loader.exec_module(bundle)
def rejected(fn):
    try:fn()
    except Exception:return
    raise AssertionError('Unsafe media was accepted')
with tempfile.TemporaryDirectory() as temporary:
    root=Path(temporary);media=root/'media';media.mkdir();(media/'engine.bin').write_bytes(b'approved executable fixture')
    private=root/'signing.pem';public=root/'trusted.pem';public.write_bytes(bundle.create(media,private))
    assert bundle.verify(media,public)=={'valid':True,'verified_files':1}
    other=root/'other.pem';other.write_bytes(bundle.create(media,root/'other-private.pem'))
    # Restore the original signature, then reject an unrelated trust root.
    public.write_bytes(bundle.create(media,private));rejected(lambda:bundle.verify(media,other))
    (media/'engine.bin').write_bytes(b'changed executable');rejected(lambda:bundle.verify(media,public))
    (media/'engine.bin').write_bytes(b'approved executable fixture');(media/'unexpected.py').write_text('unapproved');rejected(lambda:bundle.verify(media,public));(media/'unexpected.py').unlink()
    original=(media/'bundle-manifest.json').read_bytes();key=serialization.load_pem_private_key(private.read_bytes(),password=None)
    manifest=json.loads(original);manifest['files'][0]['path']='../engine.bin';raw=bundle.canonical(manifest)
    (media/'bundle-manifest.json').write_bytes(raw);(media/'bundle-signature.sig').write_bytes(key.sign(raw));rejected(lambda:bundle.verify(media,public))
    (media/'bundle-manifest.json').write_bytes(original);(media/'bundle-signature.sig').write_bytes(key.sign(original))
    (media/'copy.bin').write_bytes((media/'engine.bin').read_bytes());(media/'engine.bin').unlink();(media/'engine.bin').symlink_to(media/'copy.bin');rejected(lambda:bundle.verify(media,public))
print(json.dumps({'offline_bundle':'passed','valid_signature':True,'wrong_key':'rejected','modified_file':'rejected','unmanifested_file':'rejected','traversal':'rejected','symlink':'rejected'}))
