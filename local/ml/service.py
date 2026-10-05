"""Authenticated local AI worker. Heavy parsers run in resource-limited children."""
import asyncio,hmac,json,os,sys
from fastapi import FastAPI,Request
from fastapi.responses import JSONResponse
from .registry import inventory,public
app=FastAPI(title='SentinelCV local CV worker',docs_url=None)
semaphore=asyncio.Semaphore(int(os.getenv('SENTINEL_ML_CONCURRENCY','1')))
@app.middleware('http')
async def authorize(request,call_next):
    token=os.getenv('SENTINEL_SERVICE_TOKEN','')
    if request.url.path!='/health' and (len(token)<32 or not hmac.compare_digest(request.headers.get('x-service-token',''),token)):
        return JSONResponse({'error':'Service authentication required'},403)
    return await call_next(request)
@app.get('/health')
async def health():return {'status':'ok','models_installed':len(inventory()),'offline_only':True}
@app.get('/registry')
async def models():return {'models':[public(m) for m in inventory()]}
@app.post('/execute')
async def execute(request:Request):
    raw=await request.body()
    if len(raw)>24*1024*1024:return JSONResponse({'error':'CV job exceeds request limit'},413)
    try:body=json.loads(raw)
    except ValueError:return JSONResponse({'error':'Invalid CV job'},400)
    if body.get('operation') not in ('identity','inspect','infer','probes','dataset','drift'):return JSONResponse({'error':'Unknown CV operation'},400)
    async with semaphore:
        env=dict(os.environ,HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
        process=await asyncio.create_subprocess_exec(sys.executable,'-m','local.ml.runner',stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,env=env)
        try:out,err=await asyncio.wait_for(process.communicate(raw),timeout=210)
        except asyncio.TimeoutError:
            process.kill();await process.wait();return JSONResponse({'error':'CV analysis exceeded its time limit'},504)
        lines=[line[len(b'SENTINEL_RESULT:'):] for line in out.splitlines() if line.startswith(b'SENTINEL_RESULT:')]
        if not lines:return JSONResponse({'error':'CV worker failed; check installed dependencies and model inventory'},503)
        result=json.loads(lines[-1])
        return JSONResponse(result.get('result',{'error':result.get('error','CV analysis failed')}),200 if result.get('ok') else 422)
