"""Opt-in UI acceptance: real FastAPI routes and temporary DB, labeled external fixtures."""
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit
import json
import os
import pytest
from app.database import SessionLocal
from app.models.community import NewsArticle, NewsSource
from app.services import content_network, news_images, chinese_news
from test_community_v2 import add_source

pytestmark = pytest.mark.skipif(os.environ.get('PENGZHI_BROWSER_TESTS') != '1', reason='Requires Vite')
OUT = Path(__file__).resolve().parents[2] / '.run/news-original-images'


def test_article_artwork_browser(client, monkeypatch):
    from playwright.sync_api import sync_playwright, expect
    expect.set_options(timeout=20000)
    OUT.mkdir(parents=True, exist_ok=True)
    checks, errors, calls = [], [], []
    news_images._cache.clear()
    source = add_source(client)
    user = client.get('/api/auth/me').json()['data']
    urls = [f'https://www.moa.gov.cn/xw/zwdt/202610/t20261015_{100+i}.htm' for i in range(5)]
    titles = ['隔离验收：番茄原文有图', '隔离验收：甜瓜列表原图', '隔离验收：无正文图片', '隔离验收：原图失效', '隔离验收：网络失败']
    def fetch(url, **kwargs):
        i = urls.index(url)
        if i == 4: raise TimeoutError('fixture')
        html = '<article>只有文字</article>' if i == 2 else f'<article><img src="https://artwork.example.org/{i}.jpg" alt="隔离验收图片"></article>'
        return html.encode(), {'content-type': 'text/html'}, url, 200
    monkeypatch.setattr(content_network, 'fetch', fetch)
    monkeypatch.setattr(chinese_news, 'public_headlines', lambda: {
        'items': [{'title': title, 'url': url, 'source': '隔离验收栏目（非新闻）', 'published_at': f'2026-10-{19-i:02}'} for i, (title, url) in enumerate(zip(titles, urls))],
        'sources': [{'status': 'ok'}], 'fetched_at': datetime.now(UTC).isoformat()})
    with SessionLocal() as db:
        org = db.get(NewsSource, source['id']).organization_id
        for i, (title, url) in enumerate(zip(titles, urls)):
            db.add(NewsArticle(organization_id=org, source_id=source['id'], title=title, canonical_url=url,
                summary='隔离验收摘要，不是真实新闻。', tags=['muskmelon' if i == 1 else 'tomato'],
                published_at=datetime(2026, 10, 19)-timedelta(days=i), status='metadata_only', analysis={}))
        db.commit()
    def forward(route):
        req = route.request
        parsed = urlsplit(req.url)
        path = parsed.path + ('?' + parsed.query if parsed.query else '')
        calls.append((req.method, path))
        response = client.request(req.method, path, content=req.post_data_buffer,
            headers={k:v for k,v in req.headers.items() if k.lower() in ('authorization', 'content-type')})
        route.fulfill(status=response.status_code, body=response.content, content_type='application/json')
    def artwork(route):
        if route.request.url.endswith('/3.jpg'):
            route.fulfill(status=404, body='missing')
        else:
            route.fulfill(content_type='image/svg+xml', body='<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360"><rect width="640" height="360" fill="#b4c7a2"/><text x="40" y="180" font-size="32">ISOLATED IMAGE FIXTURE</text></svg>')
    def check(name):
        checks.append(name)
        print('PASS', name, flush=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge')
        context = browser.new_context(viewport={'width':1440, 'height':1000})
        context.route('http://127.0.0.1:5173/api/**', forward)
        context.route('https://artwork.example.org/**', artwork)
        token = client.headers['Authorization'].split(' ', 1)[1]
        context.add_init_script('localStorage.setItem("pengzhi_auth_token",'+json.dumps(token)+');localStorage.setItem("pengzhi_auth_user",'+json.dumps(json.dumps(user))+');')
        page = context.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto('http://127.0.0.1:5173/platform/news')
        expect(page.locator('.news-editorial-row')).to_have_count(4)
        feature = page.locator('.news-feature-photo .news-artwork')
        expect(feature).to_have_attribute('data-image-kind', 'original')
        expect(feature.locator('img')).to_have_js_property('complete', True)
        assert feature.locator('img').evaluate('e=>e.naturalWidth') > 0
        assert feature.locator('img').get_attribute('referrerpolicy') == 'no-referrer'
        check('头版通过正式账号接口显示原文图片')
        rows = page.locator('.news-editorial-row')
        rows.nth(0).scroll_into_view_if_needed()
        expect(rows.nth(0).locator('.news-artwork')).to_have_attribute('data-image-kind', 'original')
        check('列表通过正式账号接口显示原文图片')
        for i, name in [(1, '无图'), (2, '图片404'), (3, '原文请求失败')]:
            rows.nth(i).scroll_into_view_if_needed()
            expect(rows.nth(i).locator('.news-artwork')).to_have_attribute('data-image-kind', 'category')
            expect(rows.nth(i).locator('.news-category-art')).to_be_visible()
            check(name+'稳定使用分类占位')
        page.evaluate('window.scrollTo(0,0)')
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        page.screenshot(path=str(OUT/'desktop-isolated.png'), full_page=True)
        check('桌面头版与列表无横向溢出')
        # Real isolated API writes, never against the running production backend.
        rows.nth(0).locator('.news-row-copy h2 button').click()
        dialog = page.get_by_role('dialog', name=titles[1])
        expect(dialog).to_be_visible()
        expect(dialog).to_contain_text('隔离验收摘要')
        check('摘要阅读仍可用')
        dialog.get_by_role('button', name='收藏资讯', exact=True).click()
        expect(dialog.get_by_role('button', name='取消收藏', exact=True)).to_be_visible()
        dialog.get_by_role('button', name='Close', exact=True).click()
        page.get_by_role('button', name='我的收藏与关注', exact=True).click()
        expect(page.locator('.news-editorial-row')).to_have_count(1)
        check('正式账号收藏仍可用')
        page.get_by_role('button', name='管理关注', exact=True).click()
        drawer = page.get_by_role('dialog', name='日报与订阅管理')
        box = drawer.get_by_role('combobox', name='关注作物', exact=True)
        box.locator('xpath=ancestor::div[contains(concat(" ",normalize-space(@class)," ")," ant-select ")][1]').locator('.ant-select-selector').click()
        page.locator('.ant-select-dropdown:visible').get_by_text('甜瓜', exact=True).click()
        box.press('Escape')
        drawer.locator('button[type=submit]').filter(has_text='保存关注设置').click()
        expect(page.get_by_text('日报偏好已保存', exact=True)).to_be_visible()
        assert client.get('/api/community/news/preferences').json()['data']['crops'] == ['muskmelon']
        page.locator('.ant-drawer-close:visible').click()
        page.get_by_role('button', name='关注动态', exact=True).click()
        expect(page.locator('.news-editorial-row')).to_have_count(1)
        check('关注保存和关注动态仍可用')
        page.get_by_role('button', name='今日快讯', exact=True).click()
        expect(page.locator('.news-editorial-row')).to_have_count(4)
        page.set_viewport_size({'width':390,'height':844})
        page.evaluate('window.scrollTo(0,0)')
        page.wait_for_timeout(700)
        expect(feature).to_have_attribute('data-image-kind', 'original')
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        page.screenshot(path=str(OUT/'mobile-isolated.png'), full_page=True)
        check('手机头版与列表无横向溢出')
        guest = browser.new_context(viewport={'width':1440,'height':1000})
        guest.route('http://127.0.0.1:5173/api/**', forward)
        guest.route('https://artwork.example.org/**', artwork)
        g = guest.new_page()
        g.on('pageerror', lambda e: errors.append(str(e)))
        baseline = len(calls)
        g.goto('http://127.0.0.1:5173/platform/news?mode=guest&greenhouse_id=101')
        expect(g.locator('.news-feature-photo .news-artwork')).to_have_attribute('data-image-kind', 'original')
        assert any('/community-public/news/article-image?' in path for _,path in calls[baseline:])
        check('游客通过公开接口显示原图')
        assert not any(method not in ('GET','OPTIONS') for method,_ in calls[baseline:])
        check('游客未产生正式业务写入')
        # Test transport failure in browser rather than just a service fallback.
        guest.route('**/community-public/news/article-image?**', lambda route: route.abort())
        g.reload()
        expect(g.locator('.news-feature-photo .news-artwork')).to_have_attribute('data-image-kind', 'category')
        check('浏览器配图接口断网显示占位')
        assert not errors, errors
        check('无JavaScript运行错误')
        browser.close()
    (OUT/'browser-results.json').write_text(json.dumps({'passed':len(checks),'checks':checks,'errors':errors,
        'data':'FastAPI TestClient + temporary DB; synthetic HTML/images only in routed browser acceptance'}, ensure_ascii=False, indent=2), encoding='utf-8')
