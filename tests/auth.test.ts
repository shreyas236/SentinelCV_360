import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,readFile,readdir,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {database,objects} from '../local/storage.ts';
import {authentication,sessionActor} from '../core/auth.ts';
import {Store} from '../core/storage.ts';
import {dispatch} from '../core/engine.ts';
test('Workspace password accounts enforce fixed roles, ownership, lockout, sessions and CSRF',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'sentinel-auth-')),DB=database(dir+'/db.sqlite');
 for(const f of (await readdir('drizzle')).filter(f=>f.endsWith('.sql')).sort())DB.exec(await readFile('drizzle/'+f,'utf8'));
 const env={DB,BUCKET:objects(dir+'/objects'),KEYSTORE_SECRET:'a'.repeat(64)},password='private-test-password-2026';let cookie='';
 const req=(path:string,body?:any,headers:any={})=>new Request('https://sentinel.test/api/auth/'+path,{method:body?'POST':'GET',headers:{'content-type':'application/json',cookie,...headers},...(body?{body:JSON.stringify(body)}:{})});
 const call=(path:string,body?:any,headers:any={})=>authentication(req(path,body,headers),env,'owner-platform-user');
 try{
  assert.equal((await (await call('me')).json() as any).setup_required,true);
  assert.equal((await call('setup',{username:'admin',password})).status,201);
  assert.equal((await call('setup',{username:'otheradmin',password})).status,409);
  let r=await call('login',{username:'admin',password,account_role:'admin'});assert.equal(r.status,200);cookie=r.headers.get('set-cookie')!.split(';')[0];
  assert.ok(r.headers.get('set-cookie')!.includes('HttpOnly'));assert.ok(r.headers.get('set-cookie')!.includes('Secure'));
  assert.equal((await sessionActor(req('me'),env))!.role,'administrator');
  const u=await call('users',{username:'user-one',password,account_role:'user'});assert.equal(u.status,201);
  const c=await call('users',{username:'client-one',password,account_role:'client'});assert.equal(c.status,201);const client:any=await c.json();assert.ok(client.contributor_id);
  assert.equal((await call('users',{username:'badrole',password,account_role:'root'})).status,400);
  assert.equal((await call('users',{username:'cross-origin',password,account_role:'admin'},{origin:'https://evil.test'})).status,403);
  const logout=await authentication(new Request('https://sentinel.test/api/auth/logout',{method:'POST',headers:{cookie}}),env,'owner-platform-user');
  assert.equal(logout.status,200);assert.equal(await sessionActor(req('me'),env),null);
  r=await call('login',{username:'client-one',password,account_role:'admin'});assert.equal(r.status,401);
  r=await call('login',{username:'client-one',password,account_role:'client'});assert.equal(r.status,200);cookie=r.headers.get('set-cookie')!.split(';')[0];
  assert.equal((await call('users')).status,403);
  const actor=(await sessionActor(req('me',undefined,{'x-sentinel-demo-role':'administrator'}),env))!;assert.equal(actor.role,'contributor');
  await assert.rejects(dispatch(new Store(env),actor,'policy',{profile:'STRICT'}),/FORBIDDEN/);
  const state=await dispatch(new Store(env),actor,'state');assert.equal(state.actor.id,client.id);assert.equal(state.entities.length,1);
  cookie='';for(let i=0;i<5;i++)assert.equal((await call('login',{username:'user-one',password:'wrong'})).status,401);
  assert.equal((await call('login',{username:'user-one',password,account_role:'user'})).status,429);
  console.log(JSON.stringify({fixed_account_roles:'passed',client_ownership:'passed',forged_role_header:'rejected',csrf:'rejected',logout:'passed',account_lockout:'passed'}));
 }finally{DB.close();await rm(dir,{recursive:true,force:true});}
});
