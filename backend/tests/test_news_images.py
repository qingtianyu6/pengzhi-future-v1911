"""Article artwork tests use only synthetic HTML and pytest's temporary DB."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import threading
from unittest.mock import Mock

import httpx
import pytest
from app.services import content_network, news_images
from app.services.errors import ServiceError
from app.database import SessionLocal
from app.models.community import NewsArticle, NewsSource
from test_community_v2 import add_source, register

URL = 'https://www.moa.gov.cn/xw/zwdt/202610/t20261015_6488640.htm'


@pytest.fixture(autouse=True)
def clean_image_cache():
    news_images._cache.clear()
    news_images._inflight.clear()
    yield
    news_images._cache.clear()


@pytest.mark.parametrize('html,expected', [
    ('<meta property="og:image" content="/metadata.jpg"><article><img src="./body.jpg"></article>', 'https://www.moa.gov.cn/xw/zwdt/202610/body.jpg'),
    ('<div class="TRS_Editor"><img src="../photo.jpg"></div>', 'https://www.moa.gov.cn/xw/zwdt/photo.jpg'),
    ('<article><img src="/loading.gif" data-original="/real.jpg"></article>', 'https://www.moa.gov.cn/real.jpg'),
    ('<article><img src="data:image/gif;base64,AAAA" data-src="/lazy.jpg"></article>', 'https://www.moa.gov.cn/lazy.jpg'),
    ('<article><img data-lazy-src="//cdn.example.org/photo.jpg"></article>', 'https://cdn.example.org/photo.jpg'),
    ('<article><img srcset="/small.jpg 640w, /big.jpg 1280w"></article>', 'https://www.moa.gov.cn/small.jpg'),
    ('<meta name="twitter:image" content="/share.jpg">', 'https://www.moa.gov.cn/share.jpg'),
    ('<div id="article-content"><img alt src="/bare-alt.jpg"></div>', 'https://www.moa.gov.cn/bare-alt.jpg'),
])
def test_body_relative_lazy_and_metadata(html, expected):
    assert news_images.extract(html.encode(), URL)[0] == expected


@pytest.mark.parametrize('html', [
    '<header><img src="/website.jpg"></header><article>Text only</article>',
    '<article><img src="/logo.png"><img src="/qrcode.jpg"></article>',
    '<article><img src="/photo.jpg" alt="扫一扫关注公众号"></article>',
    '<article><img src="/pixel.png" width="1" height="1"></article>',
    '<article><img src="/icon.png" width="32px"></article>',
    '<article><footer><img src="/footer.jpg"></footer></article>',
    '<article><div class="qrcode"><img src="/unmarked.jpg"></div></article>',
    '<meta property="og:image" content="/website-logo.png">',
    '<article><img src="http://127.0.0.1/a.jpg"><img src="javascript:alert(1)"></article>',
    '<article><img src="/vector.svg"><img src="#fragment"><img src=""></article>',
])
def test_no_image_does_not_use_decoration(html):
    assert news_images.extract(html.encode(), URL) is None


@pytest.mark.parametrize('url', [
    'http://127.0.0.1/xw/qg/t20261015_1.htm',
    'https://www.moa.gov.cn.evil.org/xw/qg/t20261015_1.htm',
    'https://user:pass@www.moa.gov.cn/xw/qg/t20261015_1.htm',
    'https://www.moa.gov.cn:8443/xw/qg/t20261015_1.htm',
    'https://www.moa.gov.cn/other/t20261015_1.htm',
    'file:///xw/qg/t20261015_1.htm',
])
def test_public_url_restrictions_before_fetch(url, monkeypatch):
    fetch = Mock()
    monkeypatch.setattr(content_network, 'fetch', fetch)
    with pytest.raises(ServiceError):
        news_images.article_image(url, official=True)
    fetch.assert_not_called()


def test_cache_expiry_failure_and_size(monkeypatch):
    now = [1000.]
    monkeypatch.setattr(news_images.time, 'monotonic', lambda: now[0])
    fetch = Mock(return_value=(b'<article><img src="/body.jpg"></article>', {'content-type': 'text/html'}, URL, 200))
    monkeypatch.setattr(content_network, 'fetch', fetch)
    first = news_images.article_image(URL, official=True)
    assert first['status'] == 'found'
    first['status'] = 'tampered'
    assert news_images.article_image(URL, official=True)['status'] == 'found'
    assert fetch.call_count == 1
    now[0] += 3601
    fetch.side_effect = TimeoutError()
    assert news_images.article_image(URL, official=True)['status'] == 'unavailable'
    assert news_images.article_image(URL, official=True)['image_url'] is None
    assert fetch.call_count == 2
    now[0] += 61
    fetch.side_effect = None
    assert news_images.article_image(URL, official=True)['status'] == 'found'
    for i in range(260):
        news_images.article_image(f'https://example.org/{i}')
    assert len(news_images._cache) == 256


def test_no_image_and_non_html_fallback(monkeypatch):
    fetch = Mock(return_value=(b'<article>Text only</article>', {}, URL, 200))
    monkeypatch.setattr(content_network, 'fetch', fetch)
    assert news_images.article_image(URL)['status'] == 'no_image'
    assert news_images.article_image(URL)['image_url'] is None
    assert fetch.call_count == 1
    fetch.return_value = (b'pdf', {'content-type': 'application/pdf'}, URL, 200)
    assert news_images.article_image(URL + '?pdf=1')['status'] == 'unsupported'


def test_single_flight_concurrent_requests(monkeypatch):
    started, release = threading.Event(), threading.Event()
    def fetch(*args, **kwargs):
        started.set()
        assert release.wait(5)
        return b'<article><img src="/body.jpg"></article>', {}, URL, 200
    spy = Mock(side_effect=fetch)
    monkeypatch.setattr(content_network, 'fetch', spy)
    with ThreadPoolExecutor(max_workers=3) as pool:
        first = pool.submit(news_images.article_image, URL)
        assert started.wait(5)
        rest = [pool.submit(news_images.article_image, URL) for _ in range(2)]
        release.set()
        assert all(f.result()['status'] == 'found' for f in [first, *rest])
    assert spy.call_count == 1
    assert not news_images._inflight


def test_public_and_private_cache_policies_are_separate(monkeypatch):
    final = 'https://example.org/redirected'
    monkeypatch.setattr(content_network, 'fetch', lambda *a, **kw: (b'<article><img src="/photo.jpg"></article>', {}, final, 200))
    assert news_images.article_image(URL)['status'] == 'found'
    assert news_images.article_image(URL, official=True)['status'] == 'unavailable'


def test_redirect_is_validated_before_network(monkeypatch):
    requested = []
    class FakeClient:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        @contextmanager
        def stream(self, method, url, **kwargs):
            requested.append(url)
            yield httpx.Response(302, headers={'location': 'https://example.org/disallowed'}, request=httpx.Request(method, url))
    monkeypatch.setattr(content_network.httpx, 'Client', FakeClient)
    monkeypatch.setattr(content_network, 'public_url', lambda *a, **kw: (None, None))
    def validate(url):
        if url != URL:
            raise ServiceError(422, 'not official')
    with pytest.raises(ServiceError):
        content_network.fetch(URL, validate_url=validate)
    assert requested == [URL]


def test_image_endpoints_public_auth_and_organization_isolation(client, monkeypatch):
    fetch = Mock(return_value=(b'<article><img src="/photo.jpg"></article>', {'content-type': 'text/html'}, URL, 200))
    monkeypatch.setattr(content_network, 'fetch', fetch)
    source = add_source(client)
    with SessionLocal() as db:
        org = db.get(NewsSource, source['id']).organization_id
        row = NewsArticle(organization_id=org, source_id=source['id'], title='隔离配图测试（非新闻）', canonical_url=URL, summary='', tags=[], status='metadata_only', analysis={})
        db.add(row); db.commit(); aid = row.id
    path = f'/api/community/news/articles/{aid}/image'
    assert client.get(path).json()['data']['image_url'].endswith('/photo.jpg')
    other = register(client, '13900000029')
    before = fetch.call_count
    assert client.get(path, headers=other).status_code == 404
    assert fetch.call_count == before
    client.headers.clear()
    assert client.get(path).status_code == 401
    public = client.get('/api/community-public/news/article-image', params={'url': URL})
    assert public.status_code == 200 and public.json()['data']['status'] == 'found'
    assert client.get('/api/community-public/news/article-image', params={'url': 'https://example.org/article'}).status_code == 422
