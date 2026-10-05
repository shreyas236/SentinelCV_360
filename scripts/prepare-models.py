"""Run ONCE on a connected preparation workstation, never during offline startup."""
import argparse,hashlib,json,os,shutil
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--output',default='model-vault');args=parser.parse_args()
root=Path(args.output).resolve();root.mkdir(parents=True,exist_ok=True)
entries=[]
def register(model_id,name,adapter,task,location,source,license,classes=None,architecture=None,revision=None):
    p=root/location;paths=[p] if p.is_file() else sorted(f for f in p.rglob('*') if f.is_file() and '.cache' not in f.parts)
    files=[{'path':f.relative_to(root).as_posix(),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in paths]
    files.sort(key=lambda x:x['path']);digest=hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
    entries.append({'id':model_id,'name':name,'adapter':adapter,'task':task,'path':location,'source':source,'license':license,'classes':classes or [],'architecture':architecture,'revision':revision,'files':files,'sha256':digest})
from huggingface_hub import snapshot_download,HfApi,hf_hub_download
hf=HfApi()
for model_id,repo,adapter,task,license in [
 ('dinov2-small','facebook/dinov2-small','dinov2','EMBEDDING','Apache-2.0'),
 ('rtdetr-r18','PekingU/rtdetr_r18vd','rt-detr','DETECTION','Apache-2.0'),
 ('mask2former-small','facebook/mask2former-swin-small-coco-instance','mask2former','SEGMENTATION','MIT')]:
    revision=hf.model_info(repo).sha
    snapshot_download(repo,revision=revision,local_dir=str(root/model_id),allow_patterns=['*.json','*.safetensors','*.txt','*.model'])
    from transformers import AutoConfig
    config=AutoConfig.from_pretrained(str(root/model_id),local_files_only=True,trust_remote_code=False)
    classes=[v for k,v in sorted(config.id2label.items())] if hasattr(config,'id2label') else []
    register(model_id,model_id,adapter,task,model_id,'https://huggingface.co/'+repo,license,classes,revision=revision)
clip_repo='laion/CLIP-ViT-B-32-laion2B-s34B-b79K';revision=hf.model_info(clip_repo).sha
source=hf_hub_download(clip_repo,'open_clip_pytorch_model.bin',revision=revision)
shutil.copyfile(source,root/'openclip-vit-b32.bin')
register('openclip-vit-b32','OpenCLIP ViT B/32','openclip','EMBEDDING','openclip-vit-b32.bin','https://huggingface.co/'+clip_repo,'MIT',architecture='ViT-B-32',revision=revision)
import torch,torchvision.models as models
for name,adapter,weights in [('resnet18','resnet',models.ResNet18_Weights.IMAGENET1K_V1),('convnext_tiny','convnext',models.ConvNeXt_Tiny_Weights.IMAGENET1K_V1)]:
    model=getattr(models,name)(weights=weights).eval();location=name+'.pt';torch.save(model.state_dict(),root/location)
    register(name,name,adapter,'CLASSIFICATION',location,weights.url,'BSD-3-Clause',weights.meta['categories'],architecture=name)
from ultralytics import YOLO
model=YOLO('yolo11n.pt');shutil.copyfile(model.ckpt_path,root/'yolo11n.pt')
register('yolo11n','YOLO11n','yolo','DETECTION','yolo11n.pt','https://github.com/ultralytics/assets','AGPL-3.0',[model.names[i] for i in sorted(model.names)])
(root/'manifest.json').write_text(json.dumps({'format':'sentinel.model-vault.v1','models':entries},indent=2))
print(json.dumps({'models':len(entries),'manifest':str(root/'manifest.json'),'runtime_downloads':False}))
