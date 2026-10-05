"""Queued scans use the authenticated initiating identity; no client role headers."""
import os,httpx
from celery import Celery
celery_app=Celery('sentinel',broker=os.environ['SENTINEL_REDIS_URL'],backend=os.environ['SENTINEL_REDIS_URL'])
celery_app.conf.update(task_serializer='json',result_serializer='json',accept_content=['json'],task_time_limit=300,result_expires=3600,worker_prefetch_multiplier=1)
@celery_app.task(name='sentinel.assessment')
def assessment(action,payload,actor):
    if action not in ('scan_dataset','scan_model','benchmark','report','drift'):raise ValueError('Unsupported background task')
    with httpx.Client(timeout=280,trust_env=False) as c:
        r=c.post(os.environ['SENTINEL_API_INTERNAL_URL']+'/internal/task',headers={'x-service-token':os.environ['SENTINEL_SERVICE_TOKEN']},json={'action':action,'payload':payload,'actor':actor})
        r.raise_for_status();return r.json()
