"""Opt-in real RSS/model smoke check; writes only a fresh isolated test database."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

root = Path(__file__).resolve().parents[2]
out = root / '.run/news-automation'
out.mkdir(parents=True, exist_ok=True)
parser = argparse.ArgumentParser()
parser.add_argument('--allow-model', action='store_true', required=True)
parser.parse_args()
database = out / f'live-{int(time.time())}.db'
assert database.resolve().parent == out.resolve() and not database.exists()
os.environ['DATABASE_URL'] = 'sqlite:///' + database.as_posix()
sys.path.insert(0, str(root / 'backend'))

from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models.community import NewsAutomation, NewsArticle
from sqlalchemy import select

report = {'database': database.name, 'model_call_limit': 1}
with TestClient(app) as client:
    auth = client.post('/api/auth/register', json={'display_name':'隔离农讯实测',
        'phone':'135'+str(int(time.time()) % 100000000).zfill(8), 'password':'IsolatedNews2026'}).json()['data']
    client.headers['Authorization'] = 'Bearer ' + auth['token']
    configured = client.post('/api/community/news/automation/setup', json={
        'enabled':True, 'use_ai':True, 'ai_authorized':True, 'daily_ai_limit':1,
        'digest_limit':5, 'source_keys':['sciencedaily-agriculture'],
        'permission_confirmed':True, 'local_hour':8})
    assert configured.status_code == 200, configured.text
    try:
        first = client.post('/api/community/news/automation/run')
        assert first.status_code == 200, first.text
        report['first'] = first.json()['data']
        second = client.post('/api/community/news/automation/run')
        assert second.status_code == 200, second.text
        report['second'] = second.json()['data']
        with SessionLocal() as db:
            report['analyzed'] = [{'title':a.title, 'url':a.canonical_url, 'summary':a.summary,
                'analysis':a.analysis} for a in db.scalars(select(NewsArticle)) if a.analysis.get('summary_version')]
        report['digest_count'] = len(client.get('/api/community/news/digests').json()['data'])
        report['success'] = bool(report['analyzed']) and report['digest_count'] == 1 and report['second']['settings']['calls_reserved_today'] == 1
    finally:
        # Never leave opt-in paid work enabled after this smoke check.
        with SessionLocal() as db:
            for config in db.query(NewsAutomation):config.enabled=False
            db.commit()
        (out/'live-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'success':report.get('success',False),'analyzed':len(report.get('analyzed',[])),
    'digest_count':report.get('digest_count',0),'report':str(out/'live-result.json')},ensure_ascii=False))
sys.exit(0 if report.get('success') else 1)
