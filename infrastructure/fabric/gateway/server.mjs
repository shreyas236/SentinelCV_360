import {createServer} from 'node:http';
import {readFile,readdir} from 'node:fs/promises';
import {createPrivateKey,timingSafeEqual} from 'node:crypto';
import * as grpc from '@grpc/grpc-js';
import {connect,hash,signers} from '@hyperledger/fabric-gateway';
const token=process.env.SENTINEL_SERVICE_TOKEN??'';
if(token.length<32)throw new Error('Ledger service token is required');
const tls=await readFile(process.env.FABRIC_TLS_CERT);
let keyPath=process.env.FABRIC_PRIVATE_KEY;
if(!keyPath){const directory=process.env.FABRIC_KEY_DIRECTORY;const keys=await readdir(directory);if(keys.length!==1)throw new Error('Identity requires one signing key');keyPath=directory+'/'+keys[0];}
const identity={mspId:process.env.FABRIC_MSP_ID??'Org1MSP',credentials:await readFile(process.env.FABRIC_CERTIFICATE)};
const client=new grpc.Client(process.env.FABRIC_PEER_ENDPOINT??'peer0.org1.example.com:7051',grpc.credentials.createSsl(tls),{'grpc.ssl_target_name_override':process.env.FABRIC_PEER_HOST??'peer0.org1.example.com'});
const gateway=connect({client,identity,signer:signers.newPrivateKeySigner(createPrivateKey(await readFile(keyPath))),hash:hash.sha256,
 evaluateOptions:()=>({deadline:Date.now()+10000}),endorseOptions:()=>({deadline:Date.now()+15000}),submitOptions:()=>({deadline:Date.now()+10000}),commitStatusOptions:()=>({deadline:Date.now()+60000})});
const contract=gateway.getNetwork(process.env.FABRIC_CHANNEL??'sentinel').getContract(process.env.FABRIC_CHAINCODE??'sentinel-anchor','SentinelAnchors');
const authenticated=req=>{const given=String(req.headers['x-service-token']??'');return given.length===token.length&&timingSafeEqual(Buffer.from(given),Buffer.from(token));};
const server=createServer(async(req,res)=>{
 const json=(code,value)=>{res.writeHead(code,{'content-type':'application/json','cache-control':'no-store'});res.end(JSON.stringify(value));};
 if(!authenticated(req))return json(403,{error:'Ledger service authentication required'});
 try{
  const url=new URL(req.url,'http://ledger');
  if(req.method==='GET'&&url.pathname==='/health')return json(200,JSON.parse(Buffer.from(await contract.evaluateTransaction('Ping')).toString()));
  if(req.method==='GET'&&url.pathname.startsWith('/anchors/'))return json(200,JSON.parse(Buffer.from(await contract.evaluateTransaction('GetAnchor',decodeURIComponent(url.pathname.slice(9)))).toString()));
  if(req.method!=='POST'||url.pathname!=='/anchors')return json(404,{error:'Endpoint not found'});
  const chunks=[];let size=0;for await(const chunk of req){size+=chunk.length;if(size>16384)return json(413,{error:'Anchor request exceeds limit'});chunks.push(chunk);}
  const value=JSON.parse(Buffer.concat(chunks).toString());
  const prior=await contract.evaluateTransaction('GetAnchor',value.id).catch(()=>null);
  if(prior){const existing=JSON.parse(Buffer.from(prior).toString());if(existing.digest!==value.digest||existing.signature!==value.signature)return json(409,{error:'Existing anchor cannot be changed'});return json(200,{...existing,confirmed:true,idempotent:true});}
  const transaction=await contract.newProposal('Anchor',{arguments:[JSON.stringify(value)]}).endorse();
  const commit=await transaction.submit();const status=await commit.getStatus();
  if(!status.successful)return json(502,{error:'Fabric transaction was not committed successfully',code:status.code});
  const recorded=JSON.parse(Buffer.from(await contract.evaluateTransaction('GetAnchor',value.id)).toString());
  return json(201,{...recorded,transaction_id:status.transactionId,block_number:status.blockNumber.toString(),confirmed:true});
 }catch(e){return json(502,{error:'Fabric operation failed: '+e.message});}
});
server.listen(8770,'0.0.0.0');
for(const signal of ['SIGTERM','SIGINT'])process.on(signal,()=>{server.close();gateway.close();client.close();});
