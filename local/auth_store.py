"""Shared PostgreSQL auth state in stack mode; SQLite in the npm/Uvicorn profile."""
import os, sqlite3
from pathlib import Path
DDL=[
 'CREATE TABLE IF NOT EXISTS login_sessions(token_hash TEXT PRIMARY KEY,username TEXT NOT NULL,expires DOUBLE PRECISION NOT NULL,identity_json TEXT,access_token TEXT)',
 'CREATE TABLE IF NOT EXISTS login_attempts(username TEXT PRIMARY KEY,failures INTEGER NOT NULL,locked_until DOUBLE PRECISION NOT NULL)',
 'CREATE TABLE IF NOT EXISTS oidc_states(state_hash TEXT PRIMARY KEY,verifier TEXT NOT NULL,nonce TEXT NOT NULL,expires DOUBLE PRECISION NOT NULL)',
]
class Connection:
    def __init__(self,raw,pg):self.raw=raw;self.pg=pg
    def execute(self,sql,args=()):return self.raw.execute(sql.replace('?','%s') if self.pg else sql,args)
    def __enter__(self):return self
    def __exit__(self,t,v,tb):
        if t:self.raw.rollback()
        else:self.raw.commit()
        self.raw.close()
def connect(data):
    pg=os.getenv('SENTINEL_STORAGE')=='postgres'
    if pg:
        import psycopg
        raw=psycopg.connect(os.environ['SENTINEL_DATABASE_URL'])
    else:raw=sqlite3.connect(Path(data)/'auth.sqlite')
    conn=Connection(raw,pg)
    for sql in DDL:conn.execute(sql)
    raw.commit();return conn
