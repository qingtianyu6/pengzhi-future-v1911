import json
from datetime import timedelta
from dataclasses import replace
import pytest
from sqlalchemy import select,func
from app.database import SessionLocal,initialize_database
from app.models.community import NewsArticle,NewsEvidence,NewsSource,NewsAutomation,NewsDigest,AutomationJob
from app.services import news_service as news,news_automation as auto,content_network,ai_provider
from test_community_v2 import register


def rss():
    date=news.now().strftime('%a, %d %b %Y %H:%M:%S GMT')
    return f'''<rss version="2.0"><channel><title>明确标注的自动化测试农业来源</title>
    <item><title>Tomato greenhouse observation research fixture</title><link>https://example.org/tomato-fixture</link><pubDate>{date}</pubDate>
    <description>Test fixture only. Researchers compared tomato observations and recorded humidity and sampling time. This fictional content verifies evidence capture and is not a real news report or a production recommendation.</description></item></channel></rss>'''.encode()


def configure(client,**overrides):
    payload={'enabled':True,'use_ai':False,'daily_ai_limit':2,'digest_limit':5,'source_keys':['usda-nass'],
        'permission_confirmed':True,'local_hour':8,**overrides}
    response=client.post('/api/community/news/automation/setup',json=payload)
    assert response.status_code==200,response.text
    return response.json()['data']


def fake_model(monkeypatch,fail=False):
    calls=[]
    settings=replace(auto.get_settings(),ai_api_key='test-only',ai_model='fixture-model',ai_base_url='https://example.org')
    monkeypatch.setattr(auto,'get_settings',lambda:settings)
    class Model:
        last_usage={'total_tokens':100}
        async def chat(self,messages,tools):
            calls.append(messages)
            assert 'Test fixture only' in messages[1]['content']
            if fail:raise ValueError('fixture invalid output')
            return {'content':json.dumps({'summary':'这是隔离测试摘要，只用于验证依据实际来源内容进行整理的流程。',
                'key_points':['测试观察记录及采样时间'],'tags':['tomato','technology'],'agriculture_relevant':True,
                'uncertainty':'合成RSS夹具，不代表真实农业新闻。'},ensure_ascii=False)}
    monkeypatch.setattr(ai_provider,'get_llm_provider',lambda:Model())
    return calls


def test_setup_idempotency_no_authorization_partial_write_and_preferences(client):
    bad=client.post('/api/community/news/automation/setup',json={'enabled':True,'use_ai':True,'source_keys':['usda-nass'],'permission_confirmed':True})
    assert bad.status_code==422
    assert client.get('/api/community/news/sources').json()['data']==[]
    client.put('/api/community/news/preferences',json={'crops':['tomato'],'topics':['technology'],'enabled':True,'local_hour':6})
    configure(client);configure(client)
    assert len(client.get('/api/community/news/sources').json()['data'])==1
    pref=client.get('/api/community/news/preferences').json()['data']
    assert pref['crops']==['tomato'] and pref['topics']==['technology'] and pref['local_hour']==8
    with SessionLocal() as db:initialize_database();initialize_database()


def test_collection_evidence_and_non_ai_digest_are_real_without_model_calls(client,monkeypatch):
    monkeypatch.setattr(content_network,'fetch',lambda *a,**k:(rss(),{},'https://example.org/rss',200))
    configure(client)
    response=client.post('/api/community/news/automation/run')
    assert response.status_code==200,response.text
    assert response.json()['data']['digest']['status']=='published'
    with SessionLocal() as db:
        evidence=db.scalar(select(NewsEvidence));assert evidence.kind=='feed_summary' and 'Test fixture only' in evidence.text
        digest=db.scalar(select(NewsDigest));assert '0 条已由AI' in digest.body and 'https://example.org/tomato-fixture' in digest.body
    assert client.post('/api/community/news/automation/run').json()['data']['digest']['status']=='already_published'
    assert len(client.get('/api/community/news/digests').json()['data'])==1


def test_auto_model_grounding_cache_daily_limit_and_org_scope(client,monkeypatch):
    calls=fake_model(monkeypatch)
    monkeypatch.setattr(content_network,'fetch',lambda *a,**k:(rss(),{},'https://example.org/rss',200))
    configure(client,use_ai=True,ai_authorized=True,daily_ai_limit=1)
    result=client.post('/api/community/news/automation/run')
    assert result.status_code==200,result.text
    assert len(calls)==1
    article=client.get('/api/community/news/articles').json()['data']['items'][0]
    assert article['analysis']['method']=='model_evidence_analysis' and article['analysis']['evidence_kind']=='feed_summary'
    assert article['analysis']['actual_cost'] is None
    client.post('/api/community/news/automation/run');assert len(calls)==1
    assert client.get('/api/community/news/automation').json()['data']['calls_reserved_today']==1
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(NewsDigest))==1
    other=register(client,'13900000019')
    assert client.get('/api/community/news/automation',headers=other).json()['data']['enabled'] is False
    assert client.post('/api/community/news/automation/run',headers=other).status_code==422
    assert client.get('/api/community/news/articles',headers=other).json()['data']['total']==0


def test_model_failure_keeps_evidence_and_backoff_counts_reserved_call(client,monkeypatch):
    calls=fake_model(monkeypatch,fail=True)
    monkeypatch.setattr(content_network,'fetch',lambda *a,**k:(rss(),{},'https://example.org/rss',200))
    configure(client,use_ai=True,ai_authorized=True,daily_ai_limit=2)
    client.post('/api/community/news/automation/run')
    article=client.get('/api/community/news/articles').json()['data']['items'][0]
    assert article['analysis']['auto_status']=='failed' and 'summary_version' not in article['analysis']
    assert 'Test fixture only' in article['summary']
    client.post('/api/community/news/automation/run');assert len(calls)==1
    assert client.get('/api/community/news/automation').json()['data']['calls_reserved_today']==1


def test_title_only_does_not_spend_ai_quota_and_event_dedup(client,monkeypatch):
    calls=fake_model(monkeypatch)
    configure(client,use_ai=True,ai_authorized=True)
    with SessionLocal() as db:
        source=db.scalar(select(NewsSource))
        for i in range(2):db.add(NewsArticle(organization_id=source.organization_id,source_id=source.id,
            title='番茄观察研究进展',canonical_url=f'https://example.org/{i}',summary='仅有标题'))
        db.commit()
    monkeypatch.setattr(content_network,'fetch',lambda *a,**k:(b'<rss version="2.0"><channel/></rss>',{},'https://example.org/rss',200))
    result=client.post('/api/community/news/automation/run').json()['data']
    assert not calls
    with SessionLocal() as db:
        digest=db.scalar(select(NewsDigest));assert len(digest.article_ids)==1


def test_reserved_slots_are_not_reused_after_restart_and_next_day_resets(client,monkeypatch):
    configure(client)
    with SessionLocal() as db:
        org=db.scalar(select(NewsSource.organization_id))
        assert auto.reserve_call(db,org,1)
    with SessionLocal() as db:
        assert auto.reserve_call(db,org,1) is None
    original=news.now()
    monkeypatch.setattr(news,'now',lambda:original+timedelta(days=1))
    with SessionLocal() as db:assert auto.reserve_call(db,org,1)


def test_same_day_manual_digest_refreshes_completed_summary_without_duplicate(client,monkeypatch):
    monkeypatch.setattr(content_network,'fetch',lambda *a,**k:(rss(),{},'https://example.org/rss',200))
    configure(client)
    client.post('/api/community/news/automation/run')
    with SessionLocal() as db:
        article=db.scalar(select(NewsArticle))
        article.summary='新完成的中文依据摘要，仍保留公开原文出处。'
        article.analysis={**article.analysis,'summary_version':auto.VERSION,'headline':'中文摘要标题'}
        db.commit()
    result=client.post('/api/community/news/automation/run').json()['data']
    assert result['digest']['status']=='published'
    with SessionLocal() as db:
        digests=list(db.scalars(select(NewsDigest)))
        assert len(digests)==1 and '新完成的中文依据摘要' in digests[0].body and '中文摘要标题' in digests[0].body


def test_manual_context_analysis_uses_evidence_without_invalidating_summary_cache(client,monkeypatch):
    fake_model(monkeypatch)
    monkeypatch.setattr(content_network,'fetch',lambda *a,**k:(rss(),{},'https://example.org/rss',200))
    configure(client,use_ai=True,ai_authorized=True,daily_ai_limit=1)
    client.post('/api/community/news/automation/run')
    article=client.get('/api/community/news/articles').json()['data']['items'][0]
    class ContextModel:
        async def chat(self,messages,tools):
            assert 'Test fixture only' in messages[1]['content']
            return {'content':json.dumps({'summary':'本次关联分析结果，不覆盖已缓存的来源摘要。','crops':[],
                'stages':[],'concerns':[],'relevance_reason':'尚缺大棚环境数据','uncertainty':'隔离测试'})}
    monkeypatch.setattr(ai_provider,'get_llm_provider',lambda:ContextModel())
    result=client.post(f"/api/community/news/articles/{article['id']}/analyze",json={})
    assert result.status_code==200,result.text
    stored=client.get('/api/community/news/articles').json()['data']['items'][0]
    assert stored['analysis']==article['analysis'] and stored['summary']==article['summary']


def test_legacy_metadata_articles_gain_evidence_without_duplicate_or_304(client,monkeypatch):
    configure(client)
    with SessionLocal() as db:
        source=db.scalar(select(NewsSource));source.etag='legacy-etag'
        db.add(NewsArticle(organization_id=source.organization_id,source_id=source.id,title='旧版资讯',
            canonical_url='https://example.org/tomato-fixture',summary='旧版仅有标题'))
        db.commit()
    def fetch(*args,**kwargs):
        assert 'If-None-Match' not in kwargs.get('headers',{})
        return rss(),{},'https://example.org/rss',200
    monkeypatch.setattr(content_network,'fetch',fetch)
    client.post('/api/community/news/automation/run')
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(NewsArticle))==1
        assert 'Test fixture only' in db.scalar(select(NewsEvidence)).text
