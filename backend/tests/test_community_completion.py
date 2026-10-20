from app.database import SessionLocal
from app.models.community import NewsArticle, NewsBookmark
from app.services import content_network
from sqlalchemy import select,func
from test_community_v2 import create_post,post,add_source,rss,register


def test_public_knowledge_catalog_search_and_no_private_documents(client):
    client.headers.clear()
    all_items=client.get('/api/community-public/knowledge').json()['data']['items']
    assert all_items and all(i['source_type']=='curated_local' for i in all_items)
    result=client.get('/api/community-public/knowledge',params={'q':'番茄','crop':'tomato'}).json()['data']['items']
    assert result and all('tomato' in i['crops'] for i in result)
    assert client.get('/api/community-public/knowledge',params={'q':'unknownxyz78236'}).json()['data']['items']==[]
    assert client.get('/api/community/knowledge/documents').status_code==401


def test_forum_answer_filter_and_real_interaction_sort(client):
    a=create_post(client,title='没有回复的番茄问题')
    b=create_post(client,title='已有回复的番茄问题')
    reply=post(client,f"forum/posts/{b['id']}/comments",{'body':'实际添加的一次观察建议'},201)['comments'][0]['id']
    client.put(f"/api/community/forum/posts/{b['id']}/accepted/{reply}")
    assert [p['id'] for p in client.get('/api/community/forum/posts',params={'answer':'open'}).json()['data']['items']]==[a['id']]
    assert [p['id'] for p in client.get('/api/community/forum/posts',params={'answer':'resolved'}).json()['data']['items']]==[b['id']]
    assert client.get('/api/community/forum/posts',params={'sort':'discussed'}).json()['data']['items'][0]['id']==b['id']
    client.put(f"/api/community/forum/posts/{a['id']}/reactions/like",json={'enabled':True})
    assert client.get('/api/community/forum/posts',params={'sort':'liked'}).json()['data']['items'][0]['id']==a['id']
    assert client.get('/api/community/forum/posts',params={'sort':'invalid'}).status_code==422


def test_news_source_exact_tags_batch_read_and_cross_org_isolation(client,monkeypatch):
    monkeypatch.setattr(content_network,'fetch',lambda *a,**kw:(rss(),{},'https://example.org/rss.xml',200))
    source=add_source(client)
    post(client,f"news/sources/{source['id']}/refresh")
    a=client.get('/api/community/news/articles').json()['data']['items'][0]
    with SessionLocal() as db:
        article=db.get(NewsArticle,a['id']);article.tags=['tomato','cultivation'];db.commit()
    assert client.get('/api/community/news/articles',params={'tag':'tom'}).json()['data']['total']==0
    assert client.get('/api/community/news/articles',params={'source_id':source['id'],'read_status':'unread'}).json()['data']['total']==1
    assert client.get(f"/api/community/news/articles/{a['id']}").json()['data']['source_id']==source['id']
    for _ in range(2):
        assert post(client,'news/bookmarks/batch-read',{'article_ids':[a['id'],a['id']]})['marked']==1
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(NewsBookmark))==1
    assert client.get('/api/community/news/articles',params={'read_status':'unread'}).json()['data']['total']==0
    assert client.get('/api/community/news/articles',params={'read_status':'read'}).json()['data']['total']==1
    assert client.post('/api/community/news/bookmarks/batch-read',json={'article_ids':['1']}).status_code==422
    other=register(client,'13900000018')
    assert client.get(f"/api/community/news/articles/{a['id']}",headers=other).status_code==404
    assert client.post('/api/community/news/bookmarks/batch-read',json={'article_ids':[a['id']]},headers=other).status_code==404
    assert client.get('/api/community/news/articles',params={'read_status':'read'},headers=other).json()['data']['total']==0
