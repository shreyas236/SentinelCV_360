"""Private prepared-query bridge and bounded object/vector operations."""
import base64,hmac,json,os,re,time
import boto3,psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI,Request
from fastapi.responses import JSONResponse
app=FastAPI(title='SentinelCV protected storage',docs_url=None)
bucket=os.getenv('SENTINEL_S3_BUCKET','sentinel')
s3=boto3.client('s3',endpoint_url=os.environ['SENTINEL_S3_ENDPOINT'],aws_access_key_id=os.environ['SENTINEL_S3_ACCESS_KEY'],aws_secret_access_key=os.environ['SENTINEL_S3_SECRET_KEY'],region_name='us-east-1')

def translate(sql):
    if len(sql)>10000 or ';' in sql.strip().rstrip(';'):raise ValueError('One bounded statement is required')
    value=sql.replace('?','%s')
    if re.match(r'INSERT\s+OR\s+IGNORE\s',value,re.I):value=re.sub(r'INSERT\s+OR\s+IGNORE', 'INSERT',value,flags=re.I)+' ON CONFLICT DO NOTHING'
    return value
def object_key(key):
    if not isinstance(key,str) or len(key)>512 or key.startswith('/') or any(v in ('..','') for v in key.split('/')):raise ValueError('Object key rejected')
    return key
def connection():return psycopg.connect(os.environ['SENTINEL_DATABASE_URL'],row_factory=dict_row)
@app.middleware('http')
async def protect(request,call_next):
    token=os.getenv('SENTINEL_SERVICE_TOKEN','')
    if len(token)<32 or not hmac.compare_digest(request.headers.get('x-service-token',''),token):return JSONResponse({'error':'Service authentication required'},403)
    try:return await call_next(request)
    except Exception:return JSONResponse({'error':'Protected storage operation failed'},503)
@app.get('/health')
def health():
    with connection() as c:extensions=c.execute("SELECT extname FROM pg_extension WHERE extname IN ('vector','timescaledb')").fetchall()
    s3.head_bucket(Bucket=bucket)
    return {'status':'ok','extensions':[v['extname'] for v in extensions],'objects':'available'}
def query(c,body):
    cursor=c.execute(translate(body['sql']),body.get('args',[]));mode=body.get('mode','run')
    if mode=='first':return cursor.fetchone()
    if mode=='all':return {'results':cursor.fetchall()}
    return {'meta':{'changes':cursor.rowcount}}
@app.post('/sql')
def sql(body:dict):
    with connection() as c:return query(c,body)
@app.post('/batch')
def batch(body:dict):
    if len(body.get('statements',[]))>50:raise ValueError('Transaction too large')
    # All statements share one serializable transaction; callers retry conflicts.
    with connection() as c:
        c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
        return [query(c,row) for row in body['statements']]
@app.post('/objects/put')
def put(body:dict):
    raw=base64.b64decode(body['bytes_b64'],validate=True)
    if len(raw)>64*1024*1024:raise ValueError('Object too large')
    s3.put_object(Bucket=bucket,Key=object_key(body['key']),Body=raw,ContentType=body.get('content_type') or 'application/octet-stream')
    return {'ok':True}
@app.post('/objects/get')
def get(body:dict):
    try:
        item=s3.get_object(Bucket=bucket,Key=object_key(body['key']))
        if item['ContentLength']>64*1024*1024:raise ValueError('Object too large')
        return {'found':True,'bytes_b64':base64.b64encode(item['Body'].read()).decode()}
    except s3.exceptions.NoSuchKey:return {'found':False}
@app.post('/vectors/upsert')
def vectors(body:dict):
    rows=body.get('embeddings',[])
    if len(rows)>256:raise ValueError('Vector batch too large')
    with connection() as c:
        for row in rows:
            vector=row['vector']
            if len(vector)!=384 or any(not isinstance(v,(int,float)) or not __import__('math').isfinite(v) for v in vector):raise ValueError('DINOv2-small requires 384 finite dimensions')
            c.execute('INSERT INTO ml_embeddings(asset_id,model_id,embedding) VALUES(%s,%s,%s::vector) ON CONFLICT(asset_id,model_id) DO UPDATE SET embedding=excluded.embedding',(row['asset_id'],row['model_id'],json.dumps(vector)))
    return {'written':len(rows)}
@app.post('/vectors/search')
def vector_search(body:dict):
    vector=body['vector'];limit=min(max(int(body.get('limit',10)),1),50)
    if len(vector)!=384:raise ValueError('Wrong vector dimension')
    with connection() as c:return {'neighbors':c.execute('SELECT asset_id,model_id,embedding <=> %s::vector AS distance FROM ml_embeddings WHERE model_id=%s ORDER BY embedding <=> %s::vector LIMIT %s',(json.dumps(vector),body['model_id'],json.dumps(vector),limit)).fetchall()}
@app.post('/telemetry')
def telemetry(body:dict):
    with connection() as c:c.execute('INSERT INTO monitoring_metrics(time,category,metric,value) VALUES(now(),%s,%s,%s)',(body['category'],body['metric'],float(body['value'])))
    return {'ok':True}
