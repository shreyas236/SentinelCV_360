import { Store, now, id, type Env } from './storage.ts';
import { audit, sha } from './crypto.ts';
import type { Actor } from './engine.ts';

export const accountRoles: Record<string, string> = {
  user: 'analyst', client: 'contributor', admin: 'administrator',
  supervisor: 'supervisor', operator: 'operator', auditor: 'auditor',
};
const publicAccount = (u: any) => ({ id: u.id, username: u.username, account_role: u.account_role,
  role: u.role, contributor_id: u.contributor_id, active: !!u.active });
const cookie = (r: Request) => r.headers.get('cookie')?.split(';').map(v => v.trim())
  .find(v => v.startsWith('sentinel_session='))?.slice('sentinel_session='.length) ?? '';
export async function passwordDigest(password: string, salt: string) {
  const key = await crypto.subtle.importKey('raw', new TextEncoder().encode(password), 'PBKDF2', false, ['deriveBits']);
  const bits = await crypto.subtle.deriveBits({ name: 'PBKDF2', hash: 'SHA-256', iterations: 100000,
    salt: new TextEncoder().encode(salt) }, key, 256);
  return Buffer.from(bits).toString('hex');
}
function equal(a: string, b: string) { let n = a.length ^ b.length; for (let i = 0; i < a.length; i++) n |= a.charCodeAt(i) ^ (b.charCodeAt(i) ?? 0); return n === 0; }
function credentials(body: any) {
  const username = String(body.username ?? '').trim().toLowerCase(), password = String(body.password ?? '');
  if (!/^[a-z0-9][a-z0-9._-]{2,63}$/.test(username)) throw new Error('Use a username of 3–64 letters, numbers, dots, underscores or hyphens.');
  if (password.length < 12 || password.length > 256) throw new Error('Use a password of 12–256 characters.');
  return { username, password };
}
async function createAccount(s: Store, body: any, accountRole: string) {
  if (!(accountRole in accountRoles)) throw new Error('Invalid account role');
  const { username, password } = credentials(body), salt = crypto.randomUUID(), userId = id('ACCOUNT');
  const contributorId = accountRole === 'client' ? id('CONTRIB') : null;
  const digest = await passwordDigest(password, salt);
  await s.env.DB.prepare('INSERT INTO app_users(id,username,account_role,role,password_hash,salt,contributor_id,active,created_at) VALUES(?,?,?,?,?,?,?,?,?)')
    .bind(userId, username, accountRole, accountRoles[accountRole], digest, salt, contributorId, 1, now()).run();
  if (contributorId) await s.put({ id: contributorId, kind: 'contributor', created_at: now(), name: username,
    organization: String(body.organization ?? '').slice(0,160), risk: 0, datasets: 0, sample_count: 0 });
  return publicAccount({ id: userId, username, account_role: accountRole, role: accountRoles[accountRole], contributor_id: contributorId, active: 1 });
}
export async function sessionActor(request: Request, env: Env): Promise<(Actor & { username: string; account_role: string }) | null> {
  const token = cookie(request); if (!token) return null;
  const u = await env.DB.prepare('SELECT u.* FROM app_sessions s JOIN app_users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>? AND u.active=1')
    .bind(await sha(token), Date.now()).first();
  return u ? { id: u.id, role: u.role, username: u.username, account_role: u.account_role, contributor_id: u.contributor_id ?? undefined } : null;
}
export async function authentication(request: Request, env: Env, platformId: string): Promise<Response> {
  const s = new Store(env), url = new URL(request.url), endpoint = url.pathname;
  const json = (value: any, status = 200, headers: Record<string,string> = {}) => Response.json(value, { status, headers: { 'Cache-Control': 'no-store', ...headers } });
  if (request.method === 'POST' && request.headers.get('origin') && request.headers.get('origin') !== url.origin) return json({ error: 'Origin rejected' }, 403);
  try {
    const actor = await sessionActor(request, env);
    if (endpoint === '/api/auth/me' && request.method === 'GET') {
      const count = await env.DB.prepare('SELECT COUNT(*) AS n FROM app_users').first();
      return json({ authenticated: !!actor, setup_required: count.n === 0, actor,
        roles: accountRoles, mode: 'PRIVATE WORKSPACE ACCOUNTS' });
    }
    if (endpoint === '/api/auth/users' && request.method === 'GET') {
      if (actor?.role !== 'administrator') return json({ error: 'Administrator access required' }, 403);
      return json({ users: (await env.DB.prepare('SELECT id,username,account_role,role,contributor_id,active FROM app_users ORDER BY created_at').all()).results.map(publicAccount) });
    }
    if (request.method !== 'POST') return json({ error: 'Endpoint not found' }, 404);
    const body: any = endpoint === '/api/auth/logout' ? {} : await request.json();
    if (endpoint === '/api/auth/setup') {
      if (!platformId) return json({ error: 'Site owner sign-in required' }, 403);
      // This singleton claim prevents two simultaneous first-run administrators.
      const count = await env.DB.prepare('SELECT COUNT(*) AS n FROM app_users').first();
      if (count.n) return json({ error: 'Setup is already complete. Sign in with your account.' }, 409);
      const { username, password } = credentials(body), salt = crypto.randomUUID(), userId = 'ACCOUNT-ADMIN';
      await env.DB.prepare('INSERT INTO app_users(id,username,account_role,role,password_hash,salt,contributor_id,active,created_at) VALUES(?,?,?,?,?,?,?,?,?)')
        .bind(userId, username, 'admin', 'administrator', await passwordDigest(password,salt), salt, null, 1, now()).run();
      await audit(s,userId,'administrator','ACCOUNT_PROVISIONED',userId,{platform_user:platformId,account_role:'admin'});
      return json({ ok: true, username, message: 'Administrator created. Sign in to add User and Client accounts.' }, 201);
    }
    if (endpoint === '/api/auth/login') {
      const username = String(body.username ?? '').trim().toLowerCase().slice(0,64), password = String(body.password ?? '').slice(0,257);
      const attemptKey = await sha(platformId+'|'+username), attempts = await env.DB.prepare('SELECT * FROM app_login_attempts WHERE id=?').bind(attemptKey).first();
      if (attempts?.locked_until > Date.now()) return json({ error: 'Too many attempts. Try again in 15 minutes.' }, 429);
      const u = await env.DB.prepare('SELECT * FROM app_users WHERE username=?').bind(username).first();
      const digest = await passwordDigest(password,u?.salt ?? 'unknown-account');
      if (!u?.active || !equal(digest,u.password_hash) || (body.account_role && body.account_role !== u.account_role)) {
        await env.DB.prepare('INSERT INTO app_login_attempts(id,failures,locked_until) VALUES(?,1,0) ON CONFLICT(id) DO UPDATE SET failures=CASE WHEN locked_until>0 AND locked_until<=? THEN 1 ELSE failures+1 END,locked_until=CASE WHEN failures>=4 AND locked_until=0 THEN ? WHEN locked_until>0 AND locked_until<=? THEN 0 ELSE locked_until END')
          .bind(attemptKey,Date.now(),Date.now()+900000,Date.now()).run();
        await audit(s,platformId,'unauthenticated','LOGIN_FAILED',u?.id ?? 'UNKNOWN');
        return json({ error: 'Invalid username, password or account type.' }, 401);
      }
      const token = crypto.randomUUID()+crypto.randomUUID();
      await env.DB.prepare('DELETE FROM app_login_attempts WHERE id=?').bind(attemptKey).run();
      await env.DB.prepare('DELETE FROM app_sessions WHERE expires_at<=?').bind(Date.now()).run();
      await env.DB.prepare('INSERT INTO app_sessions(token_hash,user_id,expires_at) VALUES(?,?,?)').bind(await sha(token),u.id,Date.now()+3600000).run();
      await audit(s,u.id,u.role,'LOGIN',u.id);
      return json({ ...publicAccount(u), user_id:u.id },200,{ 'Set-Cookie': `sentinel_session=${token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=3600${url.protocol==='https:'?'; Secure':''}` });
    }
    if (!actor) return json({ error: 'Sign in required' }, 401);
    if (endpoint === '/api/auth/logout') {
      await env.DB.prepare('DELETE FROM app_sessions WHERE token_hash=?').bind(await sha(cookie(request))).run();
      await audit(s,actor.id,actor.role,'LOGOUT',actor.id);
      return json({ ok:true },200,{'Set-Cookie':'sentinel_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'});
    }
    if (endpoint === '/api/auth/users') {
      if (actor.role !== 'administrator') return json({error:'Administrator access required'},403);
      const u = await createAccount(s,body,String(body.account_role));
      await audit(s,actor.id,actor.role,'ACCOUNT_PROVISIONED',u.id,{account_role:u.account_role});
      return json(u,201);
    }
    return json({ error:'Endpoint not found' },404);
  } catch (e) {
    const message = e instanceof Error ? e.message : 'Authentication failed';
    return json({error: /UNIQUE|constraint/i.test(message) ? 'That username is already in use, or setup has already completed.' : message},400);
  }
}
