import { env } from 'cloudflare:workers';
import { handle } from '../../../core/http.ts';
import { getChatGPTUser } from '../../chatgpt-auth';
import type { Env } from '../../../core/storage.ts';
import { authentication, sessionActor } from '../../../core/auth.ts';
export const dynamic='force-dynamic';
async function route(request:Request){const user=await getChatGPTUser();if(!user)return Response.json({error:'Sign in with ChatGPT to access this private Site.',platform_signin_required:true},{status:401});const origin=request.headers.get('origin');if(request.method==='POST'&&origin&&origin!==new URL(request.url).origin)return Response.json({error:'Origin rejected'},{status:403});const bindings=env as unknown as Env;if(new URL(request.url).pathname.startsWith('/api/auth/'))return authentication(request,bindings,user.userId);const actor=await sessionActor(request,bindings);if(!actor)return Response.json({error:'Sign in with your workspace username and password.'},{status:401});return handle(request,bindings,actor);}
export const GET=route;
export const POST=route;
