"use client";
import { useEffect, useState } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select';
const labels:Record<string,string>={user:'User',client:'Client',admin:'Admin',supervisor:'Supervisor',operator:'Operator',auditor:'Auditor'};
export function AccountManagement(){
 const [users,setUsers]=useState<any[]>([]),[username,setUsername]=useState(''),[password,setPassword]=useState(''),[role,setRole]=useState('user'),[busy,setBusy]=useState(false),[message,setMessage]=useState('');
 const load=async()=>{const r=await fetch('/api/auth/users');const d:any=await r.json();if(r.ok)setUsers(d.users??[]);else setMessage(d.error??'Accounts unavailable');};
 useEffect(()=>{void load();},[]);
 return <section className="panel"><div className="panel-head"><div><h2>Workspace accounts</h2><p>Create an account and assign its access.</p></div></div><form className="account-form" onSubmit={async e=>{e.preventDefault();setBusy(true);setMessage('');try{const r=await fetch('/api/auth/users',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,password,account_role:role})});const d:any=await r.json();if(!r.ok)throw new Error(d.error??'Account creation failed');setPassword('');setUsername('');setMessage('Account created. Share its credentials privately.');await load();}catch(e:any){setMessage(e.message);}finally{setBusy(false);}}}>
 <label>Username<Input value={username} onChange={e=>setUsername(e.target.value)} autoComplete="off" minLength={3} maxLength={64} required/></label>
 <label>Initial password<Input type="password" value={password} onChange={e=>setPassword(e.target.value)} autoComplete="new-password" minLength={12} maxLength={256} required/></label>
 <label>Account type<Select value={role} onValueChange={setRole}><SelectTrigger><SelectValue/></SelectTrigger><SelectContent>{Object.entries(labels).map(([v,l])=><SelectItem value={v} key={v}>{l}</SelectItem>)}</SelectContent></Select></label>
 <Button type="submit" disabled={busy}>{busy?'Creating…':'Create account'}</Button></form>{message&&<p role="status">{message}</p>}
 <div className="account-list">{users.map(u=><div className="metric-line" key={u.id}><strong>{u.username}</strong><span>{labels[u.account_role]??u.role}</span></div>)}</div></section>;
}
