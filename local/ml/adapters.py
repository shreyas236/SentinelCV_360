"""CV engines with local weights only and a common structured output schema."""
import base64,io,json,os,tempfile
from pathlib import Path
from .registry import path,digest

def image(encoded):
    from PIL import Image
    raw=base64.b64decode(encoded,validate=True)
    if len(raw)>16*1024*1024:raise ValueError('Image exceeds 16 MB')
    im=Image.open(io.BytesIO(raw));im.load()
    if im.width*im.height>16_000_000:raise ValueError('Image pixel limit exceeded')
    return im.convert('RGB')

class Adapter:
    def __init__(self,spec):
        import torch
        self.torch=torch;self.spec=spec;digest(spec)
        self.device='cpu' if os.getenv('SENTINEL_DEVICE','cpu')=='cpu' else 'cuda'
        self.kind=spec['adapter'];location=Path(spec['_ephemeral_path']) if spec.get('_ephemeral_path') else path(spec['path'])
        if self.kind in ('dinov2','rt-detr','mask2former'):
            from transformers import AutoImageProcessor,AutoModel,AutoModelForObjectDetection,Mask2FormerForUniversalSegmentation
            self.processor=AutoImageProcessor.from_pretrained(str(location),local_files_only=True,trust_remote_code=False)
            ctor={'dinov2':AutoModel,'rt-detr':AutoModelForObjectDetection,'mask2former':Mask2FormerForUniversalSegmentation}[self.kind]
            self.model=ctor.from_pretrained(str(location),local_files_only=True,trust_remote_code=False).to(self.device).eval()
        elif self.kind in ('resnet','convnext','pytorch'):
            import torchvision.models as models
            architecture=spec.get('architecture','resnet18')
            if architecture not in ('resnet18','resnet50','convnext_tiny'):raise ValueError('Unsupported safe architecture')
            self.model=getattr(models,architecture)(weights=None,num_classes=len(spec['classes'])).to(self.device).eval()
            state=torch.load(location,map_location='cpu',weights_only=True)
            self.model.load_state_dict(state,strict=True)
            weights={'resnet18':models.ResNet18_Weights.IMAGENET1K_V1,'resnet50':models.ResNet50_Weights.IMAGENET1K_V2,'convnext_tiny':models.ConvNeXt_Tiny_Weights.IMAGENET1K_V1}[architecture]
            self.processor=weights.transforms()
        elif self.kind=='openclip':
            import open_clip
            self.model,_,self.processor=open_clip.create_model_and_transforms(spec.get('architecture','ViT-B-32'),pretrained=str(location),device=self.device)
            self.model.eval();self.tokenizer=open_clip.get_tokenizer(spec.get('architecture','ViT-B-32'))
        elif self.kind=='yolo':
            from ultralytics import YOLO
            # The file must already exist; a model identifier is never passed to YOLO.
            self.model=YOLO(str(location),task='detect')
        elif self.kind=='onnx':
            import onnx,onnxruntime as ort
            obj=onnx.load(str(location),load_external_data=False)
            def check_tensors(message):
                if isinstance(message,onnx.TensorProto) and (message.data_location==onnx.TensorProto.EXTERNAL or message.external_data):raise ValueError('ONNX external data is not permitted')
                for field,value in message.ListFields():
                    if field.type!=field.TYPE_MESSAGE:continue
                    repeated=field.is_repeated if hasattr(field,'is_repeated') else field.label==field.LABEL_REPEATED
                    for child in value if repeated else [value]:check_tensors(child)
            check_tensors(obj)
            opts=ort.SessionOptions();opts.intra_op_num_threads=2;opts.inter_op_num_threads=1
            self.model=ort.InferenceSession(str(location),sess_options=opts,providers=['CPUExecutionProvider'])
            inputs=self.model.get_inputs()
            if len(inputs)!=1 or inputs[0].type!='tensor(float)':raise ValueError('ONNX adapter requires one float32 NCHW image input')
            self.input_name=inputs[0].name
        elif self.kind=='torchscript':
            self.model=torch.jit.load(str(location),map_location=self.device).eval()
            import torchvision.transforms as T
            self.processor=T.Compose([T.Resize((spec.get('input_size',224),)*2),T.ToTensor(),T.Normalize(spec.get('mean',[.485,.456,.406]),spec.get('std',[.229,.224,.225]))])
        else:raise ValueError('Unsupported model adapter')

    def classification(self,im):
        torch=self.torch
        if self.kind=='onnx':
            import numpy as np
            size=self.spec.get('input_size',224);x=np.asarray(im.resize((size,size)),dtype=np.float32)/255
            x=(x-np.asarray(self.spec.get('mean',[.485,.456,.406]),dtype=np.float32))/np.asarray(self.spec.get('std',[.229,.224,.225]),dtype=np.float32)
            y=self.model.run(None,{self.input_name:x.transpose(2,0,1)[None]})[0]
            logits=torch.as_tensor(y)
        else:logits=self.model(self.processor(im).unsqueeze(0).to(self.device))
        if isinstance(logits,(tuple,list)):logits=logits[0]
        if logits.ndim!=2 or logits.shape[0]!=1:raise ValueError('Classification output must be [1, classes]')
        probabilities=torch.softmax(logits,dim=-1)[0].detach().cpu().tolist();idx=max(range(len(probabilities)),key=probabilities.__getitem__)
        classes=self.spec['classes']
        return {'task':'CLASSIFICATION','class_id':idx,'class_name':classes[idx] if idx<len(classes) else str(idx),
                'score':probabilities[idx],'probabilities':probabilities}

    def portable(self,im):
        """Explicit tensor contracts for uploaded ONNX and TorchScript models."""
        import numpy as np
        torch=self.torch;size=int(self.spec.get('input_size',224))
        if not 16<=size<=2048:raise ValueError('Input size must be between 16 and 2048')
        task=self.spec.get('task','CLASSIFICATION');classes=self.spec.get('classes') or []
        if self.kind=='onnx':
            x=np.asarray(im.resize((size,size)),dtype=np.float32)/255
            x=(x-np.asarray([.485,.456,.406],dtype=np.float32))/np.asarray([.229,.224,.225],dtype=np.float32)
            values=self.model.run(None,{self.input_name:x.transpose(2,0,1)[None]})
            if len(values)!=1:raise ValueError('Portable contract requires one output tensor')
            out=torch.as_tensor(values[0])
        else:
            out=self.model(self.processor(im).unsqueeze(0).to(self.device))
            if isinstance(out,dict):out=out[{'CLASSIFICATION':'logits','DETECTION':'detections','SEGMENTATION':'out','EMBEDDING':'embedding'}[task]]
            if isinstance(out,(tuple,list)):
                if len(out)!=1:raise ValueError('Portable contract requires one output tensor')
                out=out[0]
        if not isinstance(out,torch.Tensor) or not bool(torch.isfinite(out).all()):raise ValueError('Output must be a finite tensor')
        out=out.detach().cpu()
        if task=='CLASSIFICATION':
            if out.ndim!=2 or out.shape[0]!=1 or out.shape[1]!=len(classes) or not classes:raise ValueError('Classification output must be [1, declared class count]')
            p=out.softmax(-1)[0].tolist();idx=max(range(len(p)),key=p.__getitem__)
            return {'task':task,'class_id':idx,'class_name':classes[idx],'score':p[idx],'probabilities':p}
        if task=='EMBEDDING':
            if out.ndim!=2 or out.shape[0]!=1 or not 1<=out.shape[1]<=8192:raise ValueError('Embedding output must be [1, dimension <= 8192]')
            vector=torch.nn.functional.normalize(out.float(),dim=-1)[0].tolist()
            return {'task':task,'embedding':vector,'dimension':len(vector)}
        if task=='DETECTION':
            if out.ndim!=3 or out.shape[0]!=1 or out.shape[2]!=6 or out.shape[1]>1000:raise ValueError('Detection output must be [1, <=1000, 6] as input-pixel xyxy, score, class')
            detections=[]
            for row in out[0].tolist():
                x1,y1,x2,y2,score,c=row;idx=int(c)
                if c!=idx or idx<0 or idx>=len(classes) or not 0<=score<=1 or not 0<=x1<=x2<=size or not 0<=y1<=y2<=size:raise ValueError('Invalid detection coordinates, score or class')
                if score>=.25:detections.append({'class_id':idx,'class_name':classes[idx],'score':score,'bbox':[x1*im.width/size,y1*im.height/size,x2*im.width/size,y2*im.height/size]})
            return {'task':task,'detections':detections}
        if task=='SEGMENTATION':
            if out.ndim!=4 or out.shape[0]!=1 or out.shape[1]!=len(classes) or not 1<=len(classes)<=65535 or max(out.shape[2:])>2048:raise ValueError('Segmentation output must be [1, declared classes, H, W] logits')
            mask=torch.nn.functional.interpolate(out.float(),size=(im.height,im.width),mode='bilinear',align_corners=False).argmax(1)[0].numpy().astype('uint16')
            buffer=io.BytesIO();np.save(buffer,mask,allow_pickle=False);ids,counts=np.unique(mask,return_counts=True)
            return {'task':task,'shape':list(mask.shape),'mask_npy_b64':base64.b64encode(buffer.getvalue()).decode(),'classes':[{'class_id':int(c),'class_name':classes[int(c)],'pixels':int(n)} for c,n in zip(ids,counts)]}
        raise ValueError('Unsupported portable model task')

    def infer(self,im,labels=None):
        torch=self.torch
        with torch.inference_mode():
            if self.kind in ('onnx','torchscript'):return self.portable(im)
            if self.kind in ('resnet','convnext','pytorch'):return self.classification(im)
            if self.kind=='dinov2':
                x=self.processor(images=im,return_tensors='pt').to(self.device)
                vector=self.model(**x).last_hidden_state[:,0,:]
                vector=torch.nn.functional.normalize(vector,dim=-1)[0].cpu().tolist()
                return {'task':'EMBEDDING','embedding':vector,'dimension':len(vector)}
            if self.kind=='openclip':
                vec=torch.nn.functional.normalize(self.model.encode_image(self.processor(im).unsqueeze(0).to(self.device)),dim=-1)
                labels=labels or self.spec.get('classes')
                if not labels:return {'task':'EMBEDDING','embedding':vec[0].cpu().tolist()}
                text=torch.nn.functional.normalize(self.model.encode_text(self.tokenizer(['a photo of '+v for v in labels]).to(self.device)),dim=-1)
                probs=(100*vec@text.T).softmax(dim=-1)[0].cpu().tolist();idx=max(range(len(probs)),key=probs.__getitem__)
                return {'task':'CLASSIFICATION','class_id':idx,'class_name':labels[idx],'score':probs[idx],'probabilities':probs,'embedding':vec[0].cpu().tolist()}
            if self.kind=='yolo':
                result=self.model.predict(im,device=self.device,verbose=False,conf=.25)[0]
                boxes=result.boxes
                detections=[{'class_id':int(c),'class_name':result.names[int(c)],'score':float(p),'bbox':[float(x) for x in b]} for b,p,c in zip(boxes.xyxy.cpu(),boxes.conf.cpu(),boxes.cls.cpu())]
                return {'task':'DETECTION','detections':detections}
            x=self.processor(images=im,return_tensors='pt').to(self.device);out=self.model(**x)
            if self.kind=='rt-detr':
                result=self.processor.post_process_object_detection(out,target_sizes=torch.tensor([[im.height,im.width]],device=self.device),threshold=.25)[0]
                return {'task':'DETECTION','detections':[{'class_id':int(c),'class_name':self.model.config.id2label[int(c)],'score':float(p),'bbox':b.cpu().tolist()} for b,p,c in zip(result['boxes'],result['scores'],result['labels'])]}
            import numpy as np
            mask=self.processor.post_process_semantic_segmentation(out,target_sizes=[(im.height,im.width)])[0].cpu().numpy().astype('uint16')
            buffer=io.BytesIO();np.save(buffer,mask,allow_pickle=False)
            labels,counts=np.unique(mask,return_counts=True)
            return {'task':'SEGMENTATION','shape':list(mask.shape),'mask_npy_b64':base64.b64encode(buffer.getvalue()).decode(),
                    'classes':[{'class_id':int(c),'class_name':self.model.config.id2label.get(int(c),str(c)),'pixels':int(n)} for c,n in zip(labels,counts)]}

def inspection(adapter):
    kind=adapter.kind
    if kind=='onnx':return {'access':'GREY BOX','inputs':[{ 'name':i.name,'shape':i.shape,'type':i.type} for i in adapter.model.get_inputs()],
        'outputs':[{'name':i.name,'shape':i.shape} for i in adapter.model.get_outputs()], 'weight_statistics':None}
    model=adapter.model.model if kind=='yolo' else adapter.model
    rows=[];count=0
    for name,p in model.named_parameters():
        data=p.detach().float();count+=p.numel()
        rows.append({'layer':name,'parameters':p.numel(),'mean':float(data.mean()),'std':float(data.std(unbiased=False)),
                     'min':float(data.min()),'max':float(data.max()),'finite':bool(adapter.torch.isfinite(data).all())})
    return {'access':'WHITE BOX','parameter_count':count,'layers':rows,'architecture':type(model).__name__,
            'activation_analysis':'AVAILABLE FOR CLASSIFICATION ADAPTERS','trigger_reconstruction':'CLASSIFICATION ONLY'}
