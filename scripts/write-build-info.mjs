import { readFile, writeFile, readdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
const digest=bytes=>createHash('sha256').update(bytes).digest('hex');
const sources={};
for(const root of ['core','local','app','db']){
 for(const name of (await readdir(root,{recursive:true})).sort()){
  if(!/\.(ts|tsx|py|json)$/.test(name)||name==='build-info.json'||name.includes('__pycache__'))continue;
  sources[root+'/'+name]=digest(await readFile(root+'/'+name));
 }
}
const pkg=JSON.parse(await readFile('package.json','utf8'));const components=[];for(const name of Object.keys(pkg.dependencies).sort()){const p=JSON.parse(await readFile('node_modules/'+name+'/package.json','utf8'));components.push({type:'library',name,version:p.version,purl:'pkg:npm/'+name+'@'+p.version});}
const python=new Map();
for(const name of ['requirements.txt','requirements-ml.txt','requirements-stack.txt']){
 for(const line of (await readFile('local/'+name,'utf8')).split('\n')){
  const match=/^([\w.-]+)(?:\[[\w,]+\])?==([\w.+-]+)/.exec(line);if(match)python.set(match[1],match[2]);
 }
}
for(const [name,version] of [...python].sort())components.push({type:'library',name,version,purl:'pkg:pypi/'+name+'@'+version});
const sbom={bomFormat:'CycloneDX',specVersion:'1.6',version:1,metadata:{component:{type:'application',name:'SentinelCV 360',version:'1.1.0'},properties:[{name:'source_digest',value:digest(JSON.stringify(sources))},{name:'inventory_scope',value:'Installed direct JavaScript dependencies and declared pinned Python dependencies; no transitive/container SBOM claim.'}]},components};
const bytes=JSON.stringify(sbom,null,2)+'\n';await writeFile('sbom.json',bytes);await writeFile('core/build-info.json',JSON.stringify({id:'BUILD-'+digest(JSON.stringify(sources)).slice(0,12),source_digest:digest(JSON.stringify(sources)),preprocessing_hash:sources['core/images.ts'],sbom_sha256:digest(bytes),sbom},null,2)+'\n');console.log('Build identity and direct dependency SBOM generated.');
