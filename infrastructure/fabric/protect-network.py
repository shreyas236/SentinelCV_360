"""Restrict the official Fabric fixture to internal networking and loopback ports."""
import argparse
from pathlib import Path
import yaml
parser=argparse.ArgumentParser();parser.add_argument('--directory',required=True);args=parser.parse_args()
count=0
for path in (Path(args.directory)/'compose').rglob('*.yaml'):
    document=yaml.safe_load(path.read_text())
    if not isinstance(document,dict):continue
    for network in document.get('networks',{}).values():
        if isinstance(network,dict) and network.get('name')=='fabric_test':network['internal']=True
    for service in document.get('services',{}).values():
        ports=[]
        for port in service.get('ports',[]):
            if isinstance(port,(str,int)):
                parts=str(port).split(':')
                if len(parts)==2:port='127.0.0.1:'+str(port)
                elif len(parts)!=3 or parts[0]!='127.0.0.1':raise ValueError('Unexpected Fabric fixture port mapping')
            elif isinstance(port,dict):port['host_ip']='127.0.0.1'
            ports.append(port)
        if ports:service['ports']=ports
    path.write_text(yaml.safe_dump(document,sort_keys=False));count+=1
if not count:raise SystemExit('Pinned Fabric Compose files not found')
print('Fabric Compose network/loopback restrictions applied to',count,'files.')
