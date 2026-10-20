"""Editorial filters use real isolated rows; no external collection or model calls."""
from datetime import datetime
from app.database import SessionLocal
from app.models.community import NewsArticle
from test_community_v2 import add_source, register


def test_news_editorial_filters_following_sort_and_scope(client):
    source=add_source(client)
    titles=[('隔离测试：温室番茄数字管理',['tomato','technology']),('隔离测试：甜瓜授粉与水肥栽培',['muskmelon','cultivation']),('隔离测试：番茄病害防治',['tomato','disease']),('隔离测试：农业政策通知',['policy'])]
    with SessionLocal() as db:
        from app.models.community import NewsSource
        org=db.get(NewsSource,source['id']).organization_id
        rows=[]
        for i,(title,tags) in enumerate(titles):
            row=NewsArticle(organization_id=org,source_id=source['id'],title=title,canonical_url=f'https://example.org/editorial/{i}',published_at=datetime(2026,10,19-i),collected_at=datetime(2026,10,16+i),tags=tags,summary='隔离数据库测试资料，不是真实农业新闻。',status='metadata_only',analysis={})
            db.add(row);db.flush();rows.append(row.id)
        db.commit()
    def listed(**params):
        response=client.get('/api/community/news/articles',params=params)
        assert response.status_code==200,response.text
        return response.json()['data']
    assert listed(theme='facility')['total']==1
    assert listed(theme='cultivation')['items'][0]['id']==rows[1]
    assert listed(theme='disease')['items'][0]['id']==rows[2]
    assert listed(theme='policy')['items'][0]['id']==rows[3]
    assert listed(sort='published')['items'][0]['id']==rows[0]
    assert listed(sort='collected')['items'][0]['id']==rows[3]
    assert client.put('/api/community/news/preferences',json={'crops':['muskmelon'],'topics':[],'enabled':False,'local_hour':8}).status_code==200
    assert [r['id'] for r in listed(following=True)['items']]==[rows[1]]
    assert listed(theme='policy',following=True)['total']==0
    assert client.put(f'/api/community/news/bookmarks/{rows[0]}',json={'bookmarked':True}).status_code==200
    assert [r['id'] for r in listed(bookmarks=True)['items']]==[rows[0]]
    assert client.get('/api/community/news/articles',params={'theme':'invalid'}).status_code==422
    assert client.get('/api/community/news/articles',params={'sort':'invalid'}).status_code==422
    other=register(client,'13900000019')
    assert client.get('/api/community/news/articles',params={'theme':'facility'},headers=other).json()['data']['total']==0
    assert client.put(f'/api/community/news/bookmarks/{rows[0]}',json={'bookmarked':True},headers=other).status_code==404
