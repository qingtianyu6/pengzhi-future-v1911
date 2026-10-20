import json
from datetime import datetime
from pathlib import Path
from sqlalchemy import select,func
from app.database import SessionLocal
from app.models.community import NewsArticle,NewsEvidence
from app.services import chinese_news,content_network,knowledge_service as knowledge


def fixture_index():
    day=datetime.now().strftime('%Y-%m-%d')
    return f'''<ul><li><a href="./202001/t20200101_123456.htm" title="番茄水肥管理技术指导（隔离测试标题）">截断标题</a><span>{day}</span></li>
    <li><a href="https://evil.example/t20200101_123456.htm">外部链接不得进入目录</a></li>
    <li><a href="./202001/t20200101_654321.htm">无日期的测试标题不得猜时间</a></li></ul>'''.encode()


def test_curated_expansion_has_unique_ids_traceable_sources_and_crop_filter(client):
    entries=knowledge.load_knowledge()
    assert len(entries)==52 and len({e['id'] for e in entries})==52
    added=[e for e in entries if e['id'].startswith('zh-')]
    assert len(added)==42
    assert len({s['url'] for e in added for s in e['sources']})==20
    assert all(e['applicability'] and e['guidance'] and e['category'] and e['sources'][0]['accessed_at'] for e in added)
    for query,crop,word in [('甜瓜授粉','muskmelon','授粉'),('番茄脐腐','tomato','脐腐'),('番茄潜叶蛾','tomato','潜叶蛾')]:
        rows=knowledge.search_knowledge(query,limit=4)
        assert rows and word in rows[0]['title'] and all(crop in r['crops'] for r in rows)
    assert not knowledge.search_knowledge('unknownxy7293')
    response=client.get('/api/community-public/knowledge',params={'crop':'muskmelon','stage':'苗期'})
    assert response.status_code==200
    assert all(not r['stages'] or '苗期' in r['stages'] for r in response.json()['data']['items'])


def test_knowledge_file_updates_are_visible_without_restarting(monkeypatch,tmp_path):
    path=tmp_path/'knowledge.json'
    path.write_text(json.dumps([{'id':'one','title':'测试资料'}]),encoding='utf-8')
    monkeypatch.setattr(knowledge,'KNOWLEDGE_FILE',path)
    assert len(knowledge.load_knowledge())==1
    path.write_text(json.dumps([{'id':'one'},{'id':'two'}]),encoding='utf-8')
    assert len(knowledge.load_knowledge())==2


def test_official_parser_reads_visible_date_not_url_and_rejects_external_links():
    rows=chinese_news.parse_index(fixture_index(),'https://www.moa.gov.cn/xw/zwdt/')
    assert len(rows)==2 and rows[0][2].date()==datetime.now().date()
    assert rows[1][2] is None
    assert rows[0][0].endswith('（隔离测试标题）') and rows[0][3]==''


def test_official_source_collects_headlines_without_fabricated_body(client,monkeypatch):
    monkeypatch.setattr(content_network,'fetch',lambda url,**k:(fixture_index(),{},url,200))
    r=client.post('/api/community/news/automation/setup',json={'enabled':True,'source_keys':['moa-official'],
        'permission_confirmed':True,'use_ai':False})
    assert r.status_code==200,r.text
    assert client.post('/api/community/news/automation/run').status_code==200
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(NewsArticle))==2
        assert db.scalar(select(func.count()).select_from(NewsEvidence))==0
        assert all('未采集或阅读文章全文' in a.summary for a in db.scalars(select(NewsArticle)))
    rejected=client.post('/api/community/news/sources',json={'name':'不支持目录','url':'https://example.org/',
        'kind':'official_index','permission_confirmed':True,'permission_note':'隔离测试'})
    assert rejected.status_code==422


def test_public_headlines_cache_is_independent_of_organization_records(client,monkeypatch):
    calls=[]
    def fetch(url,**kw):calls.append(url);return fixture_index(),{},url,200
    monkeypatch.setattr(content_network,'fetch',fetch)
    monkeypatch.setattr(chinese_news,'_cache',None);monkeypatch.setattr(chinese_news,'_expires',0)
    client.headers.clear()
    first=client.get('/api/community-public/news/public-headlines')
    assert first.status_code==200 and len(first.json()['data']['items'])==6
    assert client.get('/api/community-public/news/public-headlines').json()==first.json()
    assert len(calls)==3
    with SessionLocal() as db:assert db.scalar(select(func.count()).select_from(NewsArticle))==0


def test_public_headlines_failure_is_explicit(client,monkeypatch):
    def fail(*a,**kw):raise TimeoutError()
    monkeypatch.setattr(content_network,'fetch',fail)
    monkeypatch.setattr(chinese_news,'_cache',None);monkeypatch.setattr(chinese_news,'_expires',0)
    data=client.get('/api/community-public/news/public-headlines').json()['data']
    assert data['items']==[] and all(s['status']=='failed' for s in data['sources'])


def test_changing_catalog_selection_disables_unselected_old_catalog_sources(client):
    for keys in [['usda-nass'],['moa-official']]:
        response=client.post('/api/community/news/automation/setup',json={'enabled':False,'source_keys':keys,'permission_confirmed':True})
        assert response.status_code==200,response.text
    sources=client.get('/api/community/news/sources').json()['data']
    assert next(s for s in sources if s['kind']=='rss')['enabled'] is False
    assert next(s for s in sources if s['kind']=='official_index')['enabled'] is True
