'use strict';
const allowed=new Set(['MERKLE_ROOT','REPORT_HASH','CASE_CLOSURE','KEY_REVOCATION','ASSET_ATTESTATION','CRITICAL_DECISION']);
const crypto=require('node:crypto');
const canonical=v=>v&&typeof v==='object'?(Array.isArray(v)?'['+v.map(canonical).join(',')+']':'{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}'):JSON.stringify(v);
function validated(text){
 if(Buffer.byteLength(text)>16384)throw new Error('Anchor exceeds 16 KB');
 const a=JSON.parse(text);
 if(!/^[A-Z0-9-]{4,80}$/.test(a.id)||!allowed.has(a.kind)||!/^[a-f0-9]{64}$/.test(a.digest))throw new Error('Invalid anchor identity, kind or digest');
 if(typeof a.signature!=='string'||a.signature.length>1024||typeof a.key_id!=='string'||!Number.isFinite(Date.parse(a.created_at)))throw new Error('Signed anchor metadata required');
 const key=crypto.createPublicKey({key:Buffer.from(a.public_key??'','base64'),type:'spki',format:'der'});
 if(key.asymmetricKeyType!=='ed25519'||!a.signed_payload||!crypto.verify(null,Buffer.from(canonical(a.signed_payload)),key,Buffer.from(a.signature,'base64')))throw new Error('Anchor signature invalid');
 const bound=a.kind==='MERKLE_ROOT'?a.signed_payload.merkle_root:a.signed_payload.digest;
 if(bound!==a.digest||a.signed_payload.created_at!==a.created_at)throw new Error('Anchor digest is not bound by its signature');
 return a;
}
class Anchors {
 async Ping(ctx){return JSON.stringify({msp:ctx.clientIdentity.getMSPID(),contract:'sentinel-anchor.v1'});}
 async Anchor(ctx,text){
  if(!['Org1MSP','Org2MSP'].includes(ctx.clientIdentity.getMSPID()))throw new Error('Organization is not authorized to anchor');
  const a=validated(text),key='anchor:'+a.id,old=await ctx.stub.getState(key);
  const keyIdentity='signing-key:'+a.key_id,pinned=await ctx.stub.getState(keyIdentity);
  if(pinned.length&&pinned.toString()!==a.public_key)throw new Error('Signing key identity mismatch');
  if(!pinned.length)await ctx.stub.putState(keyIdentity,Buffer.from(a.public_key));
  if(old.length){const {transaction_id,msp,...previous}=JSON.parse(old.toString());if(JSON.stringify(previous)!==JSON.stringify(a))throw new Error('Anchor is immutable');return old.toString();}
  const value={...a,transaction_id:ctx.stub.getTxID(),msp:ctx.clientIdentity.getMSPID()};
  await ctx.stub.putState(key,Buffer.from(JSON.stringify(value)));ctx.stub.setEvent('SentinelAnchor',Buffer.from(JSON.stringify({id:a.id,digest:a.digest})));
  return JSON.stringify(value);
 }
 async GetAnchor(ctx,id){if(!/^[A-Z0-9-]{4,80}$/.test(id))throw new Error('Invalid anchor ID');const b=await ctx.stub.getState('anchor:'+id);if(!b.length)throw new Error('Anchor not found');return b.toString();}
}
module.exports={Anchors,validated};
