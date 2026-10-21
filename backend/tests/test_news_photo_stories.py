"""Photo reports retain their own article, date and image; no fixture is public news."""
from app.services import chinese_news, content_network, news_images


def test_separate_photo_reports_use_only_exact_article_images(monkeypatch):
    monkeypatch.setattr(chinese_news, '_cache', None)
    monkeypatch.setattr(chinese_news, '_expires', 0)
    news_images._cache.clear()
    photo = 'https://www.moa.gov.cn/xw/zwdt/202608/t20260828_123456.htm'
    text_only = 'https://www.moa.gov.cn/xw/zwdt/202608/t20260828_123457.htm'
    fetched = []
    def fetch(url, **kwargs):
        fetched.append(url)
        if url == chinese_news.PHOTO_INDEX:
            raw = f'<ul><li><a href="{photo}">隔离验收：有原图的图片报道</a><span>2026-08-28</span></li><li><a href="{text_only}">隔离验收：无原图的报道</a><span>2026-08-28</span></li></ul>'
        elif url == photo:
            raw = '<article><img src="./article-photo.jpg" alt="隔离验收原图"></article>'
        elif url == text_only:
            raw = '<article>隔离验收：没有图片</article>'
        else:
            raw = '<ul><li><a href="./202610/t20261020_111111.htm">隔离验收：最新文字快讯</a><span>2026-10-20</span></li></ul>'
        return raw.encode(), {'content-type':'text/html'}, url, 200
    monkeypatch.setattr(content_network, 'fetch', fetch)
    try:
        result = chinese_news.public_headlines()
        assert len(result['items']) == 3
        assert all(i['published_at'] == '2026-10-20' for i in result['items'])
        assert len(result['photo_stories']) == 1
        story = result['photo_stories'][0]
        assert story['url'] == story['image_article_url'] == photo
        assert story['image_url'] == 'https://www.moa.gov.cn/xw/zwdt/202608/article-photo.jpg'
        assert story['published_at'] == '2026-08-28'
        assert all(i['url'] != photo for i in result['items'])
        count = len(fetched)
        assert chinese_news.public_headlines() == result
        assert len(fetched) == count
    finally:
        news_images._cache.clear()
