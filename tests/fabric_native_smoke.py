"""Real two-organization Fabric 2.5 network and Gateway anchoring without Docker.

Usage: python tests/fabric_native_smoke.py --home PATH_TO_FABRIC_BIN_CONFIG_BUILDERS
Temporary certificates are for this validation network only.
"""
import argparse,io,json,os,secrets,shutil,socket,subprocess,sys,tarfile,tempfile,time
from pathlib import Path
import yaml,httpx
parser=argparse.ArgumentParser();parser.add_argument('--home',required=True);args=parser.parse_args()
ROOT=Path(__file__).resolve().parent.parent;home=Path(args.home).resolve();temp=Path(tempfile.mkdtemp(prefix='sentinel-fabric-test-'));processes=[];logs=[]
def command(name,args,env=None):
    p=subprocess.run([str(home/'bin'/name),*map(str,args)],env=env or os.environ,capture_output=True,timeout=60)
    if p.returncode:raise AssertionError(name+': '+p.stdout.decode()[-1000:]+p.stderr.decode()[-2500:])
    return p.stdout.decode().strip()
def start(args,env,name):
    f=open(temp/(name+'.log'),'wb');logs.append(f);p=subprocess.Popen(list(map(str,args)),env=env,stdout=f,stderr=f);processes.append(p);return p
def ready(port,p):
    for _ in range(200):
        if p.poll() is not None:raise AssertionError('Service stopped during startup')
        try:
            with socket.create_connection(('127.0.0.1',port),timeout=.2):return
        except OSError:time.sleep(.1)
    raise AssertionError('Service did not listen on '+str(port))
def signature(rule):return {'Type':'Signature','Rule':rule}
def implicit(rule):return {'Type':'ImplicitMeta','Rule':rule}
try:
    crypto=temp/'crypto';config={'OrdererOrgs':[{'Name':'Orderer','Domain':'example.com','Specs':[{'Hostname':'orderer','SANS':['localhost','127.0.0.1']}]}],
      'PeerOrgs':[{'Name':'Org'+str(i),'Domain':f'org{i}.example.com','EnableNodeOUs':True,'Template':{'Count':1,'SANS':['localhost','127.0.0.1']},'Users':{'Count':1}} for i in (1,2)]}
    (temp/'crypto.yaml').write_text(yaml.safe_dump(config));command('cryptogen',['generate','--config',temp/'crypto.yaml','--output',crypto])
    organizations=[];peer_paths={};ports={1:7151,2:9151}
    for i in (1,2):
        base=crypto/f'peerOrganizations/org{i}.example.com';peer_paths[i]=base/f'peers/peer0.org{i}.example.com';msp=f'Org{i}MSP'
        organizations.append({'Name':msp,'ID':msp,'MSPDir':str(base/'msp'),'Policies':{'Readers':signature(f"OR('{msp}.admin','{msp}.peer','{msp}.client')"),'Writers':signature(f"OR('{msp}.admin','{msp}.client')"),'Admins':signature(f"OR('{msp}.admin')"),'Endorsement':signature(f"OR('{msp}.peer')")},'AnchorPeers':[{'Host':'127.0.0.1','Port':ports[i]}]})
    orderer=crypto/'ordererOrganizations/example.com/orderers/orderer.example.com';ca=orderer/'tls/ca.crt'
    orderer_org={'Name':'OrdererOrg','ID':'OrdererMSP','MSPDir':str(crypto/'ordererOrganizations/example.com/msp'),'Policies':{'Readers':signature("OR('OrdererMSP.member')"),'Writers':signature("OR('OrdererMSP.member')"),'Admins':signature("OR('OrdererMSP.admin')")},'OrdererEndpoints':['127.0.0.1:7050']}
    orderer_config={'OrdererType':'etcdraft','Addresses':['127.0.0.1:7050'],'BatchTimeout':'1s','BatchSize':{'MaxMessageCount':10,'AbsoluteMaxBytes':'99 MB','PreferredMaxBytes':'512 KB'},'EtcdRaft':{'Consenters':[{'Host':'127.0.0.1','Port':7050,'ClientTLSCert':str(orderer/'tls/server.crt'),'ServerTLSCert':str(orderer/'tls/server.crt')}]},'Organizations':[orderer_org],'Policies':{'Readers':implicit('ANY Readers'),'Writers':implicit('ANY Writers'),'Admins':implicit('MAJORITY Admins'),'BlockValidation':implicit('ANY Writers')},'Capabilities':{'V2_0':True}}
    application={'Organizations':organizations,'Policies':{'Readers':implicit('ANY Readers'),'Writers':implicit('ANY Writers'),'Admins':implicit('MAJORITY Admins'),'LifecycleEndorsement':implicit('MAJORITY Endorsement'),'Endorsement':implicit('MAJORITY Endorsement')},'Capabilities':{'V2_5':True}}
    profile={'Policies':{'Readers':implicit('ANY Readers'),'Writers':implicit('ANY Writers'),'Admins':implicit('MAJORITY Admins')},'Capabilities':{'V2_0':True},'Orderer':orderer_config,'Application':application}
    (temp/'configtx.yaml').write_text(yaml.safe_dump({'Organizations':organizations+[orderer_org],'Profiles':{'SentinelGenesis':profile}}))
    env=dict(os.environ,FABRIC_CFG_PATH=str(temp));block=temp/'sentinel.block';command('configtxgen',['-profile','SentinelGenesis','-channelID','sentinel','-outputBlock',block],env)
    oc=yaml.safe_load((home/'config/orderer.yaml').read_text());oc['General'].update(ListenAddress='127.0.0.1',ListenPort=7050,BootstrapMethod='none',LocalMSPID='OrdererMSP',LocalMSPDir=str(orderer/'msp'))
    oc['General']['TLS'].update(Enabled=True,PrivateKey=str(orderer/'tls/server.key'),Certificate=str(orderer/'tls/server.crt'),RootCAs=[str(ca)])
    oc['Admin']={'ListenAddress':'127.0.0.1:7053','TLS':{'Enabled':True,'Certificate':str(orderer/'tls/server.crt'),'PrivateKey':str(orderer/'tls/server.key'),'ClientAuthRequired':True,'ClientRootCAs':[str(ca)]}}
    oc['ChannelParticipation']={'Enabled':True};oc['FileLedger']['Location']=str(temp/'orderer-ledger')
    oc['Consensus'].update(WALDir=str(temp/'raft-wal'),SnapDir=str(temp/'raft-snap'));(temp/'orderer.yaml').write_text(yaml.safe_dump(oc))
    op=start([home/'bin/orderer'],env,'orderer');ready(7053,op)
    command('osnadmin',['channel','join','--channelID','sentinel','--config-block',block,'-o','127.0.0.1:7053','--ca-file',ca,'--client-cert',orderer/'tls/server.crt','--client-key',orderer/'tls/server.key'])
    peer_envs={}
    for i in (1,2):
        configdir=temp/f'peer{i}';configdir.mkdir();pc=yaml.safe_load((home/'config/core.yaml').read_text());p=peer_paths[i];base=p.parent.parent
        pc['peer'].update(addressAutoDetect=False,id=f'peer0.org{i}.example.com',networkId='sentinel-native',listenAddress=f'127.0.0.1:{ports[i]}',address=f'127.0.0.1:{ports[i]}',localMspId=f'Org{i}MSP',mspConfigPath=str(p/'msp'),fileSystemPath=str(temp/f'peer{i}-ledger'),chaincodeListenAddress=f'127.0.0.1:{ports[i]+1}')
        pc['peer']['tls'].update(enabled=True,clientAuthRequired=False,cert={'file':str(p/'tls/server.crt')},key={'file':str(p/'tls/server.key')},rootcert={'file':str(p/'tls/ca.crt')})
        pc['peer']['gossip'].update(bootstrap='',externalEndpoint=f'127.0.0.1:{ports[i]}',useLeaderElection=False,orgLeader=True)
        pc['chaincode']['externalBuilders']=[{'name':'ccaas_builder','path':str(home/'builders/ccaas'),'propagateEnvironment':[]}]
        pc['operations']['listenAddress']=f'127.0.0.1:{9442+i}';(configdir/'core.yaml').write_text(yaml.safe_dump(pc))
        pe=dict(os.environ,FABRIC_CFG_PATH=str(configdir));pp=start([home/'bin/peer','node','start'],pe,'peer'+str(i));ready(ports[i],pp)
        pe.update(CORE_PEER_MSPCONFIGPATH=str(base/f'users/Admin@org{i}.example.com/msp'))
        command('peer',['channel','join','-b',block],pe);peer_envs[i]=pe
    package=temp/'sentinel-anchor.tar.gz';code=io.BytesIO()
    with tarfile.open(fileobj=code,mode='w:gz') as t:
        data=json.dumps({'address':'127.0.0.1:9999','dial_timeout':'10s','tls_required':False}).encode();info=tarfile.TarInfo('connection.json');info.size=len(data);t.addfile(info,io.BytesIO(data))
    with tarfile.open(package,'w:gz') as t:
        for name,data in [('metadata.json',json.dumps({'type':'ccaas','label':'sentinel_1.0'}).encode()),('code.tar.gz',code.getvalue())]:
            info=tarfile.TarInfo(name);info.size=len(data);t.addfile(info,io.BytesIO(data))
    package_id=command('peer',['lifecycle','chaincode','calculatepackageid',package],peer_envs[1]).splitlines()[-1]
    for i in (1,2):command('peer',['lifecycle','chaincode','install',package],peer_envs[i])
    shared=['-o','127.0.0.1:7050','--ordererTLSHostnameOverride','orderer.example.com','--tls','--cafile',ca,'--channelID','sentinel','--name','sentinel-anchor','--version','1.0','--sequence','1','--signature-policy',"AND('Org1MSP.peer','Org2MSP.peer')"]
    for i in (1,2):command('peer',['lifecycle','chaincode','approveformyorg',*shared,'--package-id',package_id,'--waitForEvent'],peer_envs[i])
    command('peer',['lifecycle','chaincode','commit',*shared,'--peerAddresses','127.0.0.1:7151','--tlsRootCertFiles',peer_paths[1]/'tls/ca.crt','--peerAddresses','127.0.0.1:9151','--tlsRootCertFiles',peer_paths[2]/'tls/ca.crt','--waitForEvent'],peer_envs[1])
    ccenv=dict(os.environ,CHAINCODE_SERVER_ADDRESS='127.0.0.1:9999',CHAINCODE_ID=package_id,CORE_CHAINCODE_ID_NAME=package_id)
    cp=start(['node',ROOT/'infrastructure/fabric/chaincode/node_modules/fabric-shim/cli.js','server','--module-path',ROOT/'infrastructure/fabric/chaincode'],ccenv,'chaincode');ready(9999,cp)
    p=peer_paths[1];base=p.parent.parent;secret=secrets.token_hex(32)
    genv=dict(os.environ,SENTINEL_SERVICE_TOKEN=secret,FABRIC_TLS_CERT=str(p/'tls/ca.crt'),FABRIC_PEER_ENDPOINT='127.0.0.1:7151',FABRIC_PEER_HOST='peer0.org1.example.com',FABRIC_CERTIFICATE=str(base/'users/Admin@org1.example.com/msp/signcerts/Admin@org1.example.com-cert.pem'),FABRIC_KEY_DIRECTORY=str(base/'users/Admin@org1.example.com/msp/keystore'))
    gp=start(['node',ROOT/'infrastructure/fabric/gateway/server.mjs'],genv,'gateway');ready(8770,gp)
    headers={'x-service-token':secret}
    for _ in range(100):
        response=httpx.get('http://127.0.0.1:8770/health',headers=headers,trust_env=False,timeout=15)
        if response.status_code==200:break
        time.sleep(.2)
    assert response.status_code==200,response.text
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    import base64
    signing_key=Ed25519PrivateKey.generate();signed_payload={'merkle_root':'a'*64,'created_at':'2026-10-04T00:00:00Z'}
    anchor={'id':'ANCHOR-NATIVE-TEST','kind':'MERKLE_ROOT','digest':'a'*64,'signature':base64.b64encode(signing_key.sign(json.dumps(signed_payload,sort_keys=True,separators=(',',':')).encode())).decode(),'signed_payload':signed_payload,'public_key':base64.b64encode(signing_key.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)).decode(),'key_id':'SERVICE','created_at':'2026-10-04T00:00:00Z'}
    response=httpx.post('http://127.0.0.1:8770/anchors',headers=headers,json=anchor,trust_env=False,timeout=90);assert response.status_code==201,response.text
    receipt=response.json();assert receipt['confirmed'] and receipt['block_number']
    get=httpx.get('http://127.0.0.1:8770/anchors/'+anchor['id'],headers=headers,trust_env=False);assert get.json()['digest']==anchor['digest']
    retry=httpx.post('http://127.0.0.1:8770/anchors',headers=headers,json=anchor,trust_env=False);assert retry.status_code==200
    bad=httpx.post('http://127.0.0.1:8770/anchors',headers=headers,json={**anchor,'digest':'b'*64},trust_env=False);assert bad.status_code==409
    result={'fabric_version':'2.5.12','organizations':2,'peer_count':2,'orderer_count':1,'real_ledger_commit':'passed','gateway_requery':'passed','immutable_anchor':'passed','transaction_id':receipt['transaction_id'],'block_number':receipt['block_number'],'scope':'Native processes; ephemeral test certificates; not the Docker Compose deployment'}
    (ROOT/'docs/fabric-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
except Exception:
    for f in temp.glob('*.log'):
        print(f.name+': '+f.read_text(errors='replace')[-2000:],file=sys.stderr)
    raise
finally:
    for p in reversed(processes):
        p.terminate()
        try:p.wait(timeout=5)
        except subprocess.TimeoutExpired:p.kill();p.wait()
    for f in logs:f.close()
    shutil.rmtree(temp,ignore_errors=True)
