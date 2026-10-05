import {generateKeyPairSync,sign} from 'node:crypto';
import {canonical} from '../core/crypto.ts';
import test from 'node:test';import assert from 'node:assert/strict';import{createRequire}from'node:module';
const require=createRequire(import.meta.url);const{Anchors}=require('../infrastructure/fabric/chaincode/anchors.cjs');
test('Fabric contract rejects unauthorized, malformed and overwritten anchors',async()=>{
 const ledger=new Map();const ctx={clientIdentity:{getMSPID:()=> 'Org1MSP'},stub:{getState:async(k:string)=>ledger.get(k)??Buffer.alloc(0),putState:async(k:string,v:any)=>ledger.set(k,v),getTxID:()=> 'real-stub-transaction',setEvent:()=>{}}};
 const contract=new Anchors();const keys=generateKeyPairSync('ed25519');const signed_payload={merkle_root:'a'.repeat(64),created_at:new Date().toISOString()};const anchor={id:'ANCHOR-1234',kind:'MERKLE_ROOT',digest:signed_payload.merkle_root,signature:sign(null,Buffer.from(canonical(signed_payload)),keys.privateKey).toString('base64'),key_id:'SERVICE',created_at:signed_payload.created_at,signed_payload,public_key:keys.publicKey.export({format:'der',type:'spki'}).toString('base64')};
 const receipt=JSON.parse(await contract.Anchor(ctx,JSON.stringify(anchor)));assert.equal(receipt.digest,anchor.digest);assert.equal(ledger.size,2);
 assert.equal(JSON.parse(await contract.GetAnchor(ctx,anchor.id)).transaction_id,'real-stub-transaction');
 const changed={...signed_payload,merkle_root:'b'.repeat(64)};await assert.rejects(contract.Anchor(ctx,JSON.stringify({...anchor,digest:'b'.repeat(64),signed_payload:changed,signature:sign(null,Buffer.from(canonical(changed)),keys.privateKey).toString('base64')})),/immutable/);
 await assert.rejects(contract.Anchor(ctx,JSON.stringify({...anchor,signature:'corrupt'})),/signature invalid/);
 await assert.rejects(contract.Anchor({...ctx,clientIdentity:{getMSPID:()=> 'UnknownMSP'}},JSON.stringify(anchor)),/authorized/);
 await assert.rejects(contract.Anchor(ctx,JSON.stringify({...anchor,id:'../escape'})),/Invalid/);
});
