import { Store, now } from './storage.ts';
import { sha, canonical, sign, ensureKey, audit } from './crypto.ts';
import type { Actor } from './engine.ts';
export async function aiCall(s:Store,body:any){
 if(!s.env.LOCAL_MODE||!s.env.AI_SERVICE_URL)throw new Error('Local CV worker is not configured. Start the Ubuntu ML profile and install its model vault.');
 const response=await fetch(s.env.AI_SERVICE_URL+'/execute',{method:'POST',headers:{'Content-Type':'application/json','x-service-token':s.env.SERVICE_TOKEN??''},body:JSON.stringify(body),signal:AbortSignal.timeout(215000)});
 const data:any=await response.json();if(!response.ok)throw new Error(data.error??'CV worker rejected the analysis');return data;
}
export async function installedModels(s:Store){if(!s.env.LOCAL_MODE||!s.env.AI_SERVICE_URL)return [];
 const r=await fetch(s.env.AI_SERVICE_URL+'/registry',{headers:{'x-service-token':s.env.SERVICE_TOKEN??''},signal:AbortSignal.timeout(10000)});
 if(!r.ok)throw new Error('Local CV registry unavailable');return ((await r.json()) as any).models;
}
export async function integrationStatus(s:Store){let models:any[]=[];let error=null;
 try{models=await installedModels(s);}catch(e){error=e instanceof Error?e.message:'CV worker unavailable';}
 return {mode:s.env.LOCAL_MODE?'LOCAL':'HOSTED',storage:s.env.STORAGE_PROFILE??(s.env.LOCAL_MODE?'SQLite / filesystem':'D1 / R2'),
  auth:s.env.AUTH_PROFILE??'Workspace password accounts',models,ai_worker:{configured:!!s.env.AI_SERVICE_URL,error},
  fabric:{configured:!!s.env.LEDGER_URL,status:s.env.LEDGER_URL?'CONFIGURED · VERIFY AN ANCHOR':'NOT CONNECTED'},
  note:'Configured services require runtime validation. No production readiness claim is made from configuration alone.'};
}
export async function registerPretrained(s:Store,a:Actor,b:any){
 if(a.role!=='administrator')throw new Error('FORBIDDEN: administrator approval required to pin a reference model');
 const registry=await installedModels(s),spec=registry.find((m:any)=>m.id===b.model_id);if(!spec)throw new Error('Select an installed model');
 const identity=await aiCall(s,{operation:'identity',model_id:spec.id});if(!identity.valid)throw new Error('Installed model does not match its prepared inventory');
 const blob='models/descriptors/'+crypto.randomUUID()+'.json';await s.blob(blob,canonical(spec),'application/json');
 const m=await s.create('model','MODEL',{name:spec.name,local_model_id:spec.id,blob,sha256:identity.sha256,format:spec.adapter,classes:spec.classes,task:spec.task,
  access:'UNASSESSED',state:'UNASSESSED',disposition:'REVIEW',risk:null,source:'LOCAL PRETRAINED MODEL VAULT'});
 const key=await ensureKey(s,'SERVICE');const ref=await s.create('reference','REF',{name:'Approved '+spec.name,asset_type:'model',model_id:m.id,local_model_id:spec.id,
  blob,sha256:identity.sha256,public_key:key.public_key,signature:await sign(s,'SERVICE',identity.sha256),approved_by:a.id,approved_at:now()});
 m.reference_id=ref.id;await s.put(m);await s.edge(ref.id,m.id,'VERIFIED_BY');await audit(s,a.id,a.role,'REFERENCE_MODEL_PINNED',m.id,{vault_id:spec.id,digest:identity.sha256});return m;
}
export async function approveUploadedModel(s:Store,a:Actor,b:any){
 if(a.role!=='administrator')throw new Error('FORBIDDEN: administrator approval required');
 const m=await s.get(b.asset_id);if(m.kind!=='model'||m.source!=='uploaded')throw new Error('Select an uploaded model reviewed by your reference authority');
 const bytes=await s.bytes(m.blob),digest=await sha(bytes);if(digest!==m.sha256)throw new Error('Uploaded model changed since registration');
 const blob='models/references/'+crypto.randomUUID();await s.blob(blob,bytes);
 const key=await ensureKey(s,'SERVICE');const ref=await s.create('reference','REF',{name:'Approved '+m.name,asset_type:'model',model_id:m.id,
  blob,sha256:digest,format:m.format,architecture:m.architecture,task:m.task,classes:m.classes,input_size:m.input_size,
  public_key:key.public_key,signature:await sign(s,'SERVICE',digest),approved_by:a.id,approved_at:now()});
 m.reference_id=ref.id;m.disposition='REVIEW';m.state='UNASSESSED';await s.put(m);await s.edge(ref.id,m.id,'VERIFIES');
 await audit(s,a.id,a.role,'UPLOADED_MODEL_REFERENCE_PINNED',m.id,{reference_id:ref.id,digest});return ref;
}
export async function samplePayload(s:Store,samples:any[],limit=128){return Promise.all(samples.slice(0,limit).map(async v=>({id:v.id,class_id:v.class_id,image_b64:Buffer.from(await s.bytes(v.blob)).toString('base64')})));}
export async function anchorLedger(s:Store,anchor:any){
 if(!s.env.LEDGER_URL)return {...anchor,external_ledger:'NOT CONNECTED'};
 const key=await ensureKey(s,'SERVICE');const signed_payload={event_count:anchor.event_count,head:anchor.head,merkle_root:anchor.merkle_root,created_at:anchor.created_at};
 const payload={id:anchor.id,kind:'MERKLE_ROOT',digest:anchor.merkle_root,head:anchor.head,event_count:anchor.event_count,signature:anchor.signature,key_id:anchor.key_id,created_at:anchor.created_at,public_key:key.public_key,signed_payload};
 const r=await fetch(s.env.LEDGER_URL+'/anchors',{method:'POST',headers:{'Content-Type':'application/json','x-service-token':s.env.SERVICE_TOKEN??''},body:JSON.stringify(payload),signal:AbortSignal.timeout(30000)});
 const receipt:any=await r.json();if(!r.ok)throw new Error('Fabric anchoring failed: '+(receipt.error??r.status));
 const saved={...anchor,external_ledger:'HYPERLEDGER FABRIC',ledger_receipt:receipt};await s.put(saved);return saved;
}
