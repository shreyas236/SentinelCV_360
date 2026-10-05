export type Env = { DB:any; BUCKET:any; KEYSTORE_SECRET:string; LOCAL_MODE?:string; AI_SERVICE_URL?:string; SERVICE_TOKEN?:string; LEDGER_URL?:string; STORAGE_PROFILE?:string; AUTH_PROFILE?:string; STORAGE_SERVICE_URL?:string };
export type Entity = { id:string; kind:string; created_at:string; [key:string]:any };
export const now=()=>new Date().toISOString();
export const id=(prefix:string)=>prefix+'-'+crypto.randomUUID().slice(0,8).toUpperCase();
export class Store {
 env:Env; constructor(env:Env){this.env=env;if(!env.DB||!env.BUCKET)throw new Error('Database or object storage unavailable.');}
 async get(key:string):Promise<Entity>{const r=await this.env.DB.prepare('SELECT data FROM entities WHERE id=?').bind(key).first();if(!r)throw new Error('Asset not found: '+key);return JSON.parse(r.data);}
 async maybe(key:string){try{return await this.get(key);}catch{return null;}}
 async list(kind?:string):Promise<Entity[]>{const q=kind?this.env.DB.prepare('SELECT data FROM entities WHERE kind=? ORDER BY created DESC').bind(kind):this.env.DB.prepare('SELECT data FROM entities ORDER BY created DESC');return (await q.all()).results.map((x:any)=>JSON.parse(x.data));}
 async put(e:Entity){await this.env.DB.prepare('INSERT INTO entities(id,kind,data,created) VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data').bind(e.id,e.kind,JSON.stringify(e),e.created_at).run();return e;}
 async create(kind:string,prefix:string,data:any){return this.put({id:id(prefix),kind,created_at:now(),...data});}
 async edge(source:string,target:string,relation:string){await this.env.DB.prepare('INSERT OR IGNORE INTO graph_edges(source,target,relation) VALUES(?,?,?)').bind(source,target,relation).run();}
 async edges(){return (await this.env.DB.prepare('SELECT source,target,relation FROM graph_edges').all()).results;}
 async blob(key:string,data:Uint8Array|string,type='application/octet-stream'){await this.env.BUCKET.put(key,data,{httpMetadata:{contentType:type}});return key;}
 async bytes(key:string){const r=await this.env.BUCKET.get(key);if(!r)throw new Error('Artifact not found.');return new Uint8Array(await r.arrayBuffer());}
}
