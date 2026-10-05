"""Bounded static ONNX metadata inspection; no inference and no checkpoint execution."""
import argparse,json,os,resource
from pathlib import Path

def inspect(path):
    resource.setrlimit(resource.RLIMIT_CPU,(15,15));resource.setrlimit(resource.RLIMIT_AS,(1024**3,1024**3))
    import onnx
    p=Path(path);data=p.read_bytes()
    if len(data)>8*1024*1024:raise ValueError('Model exceeds 8 MB inspection limit')
    model=onnx.load_model_from_string(data)
    for tensor in model.graph.initializer:
        if tensor.data_location==onnx.TensorProto.EXTERNAL or tensor.external_data:raise ValueError('External ONNX tensor data is forbidden')
    return {'format':'ONNX','static_only':True,'inference_executed':False,'inputs':[i.name for i in model.graph.input],'outputs':[o.name for o in model.graph.output],'nodes':len(model.graph.node),'initializers':len(model.graph.initializer),'operators':sorted(set(n.op_type for n in model.graph.node)),'limitation':'This utility is not connected to the workspace runtime. A hardened isolated inference adapter is still required.'}
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('model');args=parser.parse_args()
    print(json.dumps(inspect(args.model),indent=2))
