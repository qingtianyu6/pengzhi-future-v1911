"""Read public headlines and exact-article image metadata; do not retain full text."""
from datetime import datetime
from html.parser import HTMLParser
import re
from urllib.parse import urljoin, urlsplit
from app.services.errors import ServiceError
from concurrent.futures import ThreadPoolExecutor
import threading
import time

OFFICIAL_INDEXES = {
    'https://www.moa.gov.cn/xw/zwdt/',
    'https://www.moa.gov.cn/xw/qg/',
    'https://zzys.moa.gov.cn/gdxw/',
}
PHOTO_INDEX = 'https://www.moa.gov.cn/xw/tpxw20240711/'


def validate_index(url):
    if url not in OFFICIAL_INDEXES | {PHOTO_INDEX}:
        raise ServiceError(422, '官方目录采集目前仅支持推荐目录中的农业农村部栏目')


class IndexParser(HTMLParser):
    def __init__(self, base):
        super().__init__(convert_charrefs=True)
        self.base=base;self.href='';self.title='';self.text=[];self.rows=[];self.item_text=[];self.pending=[];self.in_item=False

    def handle_starttag(self,tag,attrs):
        if tag=='li':self.in_item=True;self.item_text=[];self.pending=[]
        if tag=='a':
            attrs=dict(attrs);self.href=attrs.get('href','');self.title=attrs.get('title','');self.text=[]

    def handle_data(self,data):
        if self.href:self.text.append(data)
        if self.in_item:self.item_text.append(data)

    def handle_endtag(self,tag):
        if tag=='li':
            date=re.search(r'\b(20\d{2}-\d{2}-\d{2})\b',' '.join(self.item_text))
            try:published=datetime.strptime(date[1],'%Y-%m-%d') if date else None
            except ValueError:published=None
            self.rows.extend((title,url,published,'','official_headline') for title,url in self.pending)
            self.in_item=False;self.pending=[]
        if tag!='a' or not self.href:return
        url=urljoin(self.base,self.href);title=re.sub(r'\s+',' ',self.title or ''.join(self.text)).strip()
        match=re.search(r'/t(\d{8})_\d+\.htm$',urlsplit(url).path)
        if self.in_item and match and urlsplit(url).netloc==urlsplit(self.base).netloc and len(title)>=6:
            self.pending.append((title,url))
        self.href=''


def parse_index(raw,base_url):
    validate_index(base_url)
    parser=IndexParser(base_url);parser.feed(raw.decode('utf-8-sig',errors='replace'))
    unique={r[1]:r for r in parser.rows}
    if not unique:raise ServiceError(422,'官方目录结构变化或暂无有效标题，未生成虚构资讯')
    return list(unique.values())[:80]


_cache=None
_expires=0
_lock=threading.Lock()


def public_headlines():
    """Public metadata, independent of every organization's private news records."""
    global _cache,_expires
    from app.services import content_network
    with _lock:
        if _cache is not None and time.monotonic()<_expires:return _cache
        def read(url):
            try:
                raw,_,final,_=content_network.fetch(url)
                return {'url':url,'status':'ok','rows':parse_index(raw,final)}
            except Exception as exc:return {'url':url,'status':'failed','error_type':type(exc).__name__,'rows':[]}
        with ThreadPoolExecutor(max_workers=4) as executor:results=list(executor.map(read,sorted(OFFICIAL_INDEXES | {PHOTO_INDEX})))
        items={row[1]:{'title':row[0],'url':row[1],'published_at':row[2].date().isoformat() if row[2] else None,
            'source_url':result['url'],'source':'农业农村部 · '+('全国信息联播' if '/qg/' in result['url'] else '种植业管理司' if 'zzys.' in result['url'] else '部级动态')}
            for result in results if result['url'] != PHOTO_INDEX for row in result['rows']}
        # Keep older photo reports separate from today's headlines. Only display
        # an image extracted from that exact article, never an adjacent story.
        from app.services.news_images import article_image
        candidates = next((r['rows'][:3] for r in results if r['url'] == PHOTO_INDEX), [])
        def photo(row):
            try:
                image = article_image(row[1], official=True)
                if image['status'] != 'found': return None
                return {'title': row[0], 'url': row[1], 'published_at': row[2].date().isoformat() if row[2] else None,
                        'source': '农业农村部 · 图片新闻', 'source_url': PHOTO_INDEX,
                        'image_url': image['image_url'], 'image_article_url': row[1]}
            except Exception: return None
        with ThreadPoolExecutor(max_workers=3) as executor:
            photos = [item for item in executor.map(photo, candidates) if item]
        _cache={'items':sorted(items.values(),key=lambda r:r['published_at'] or '',reverse=True)[:12],
            'photo_stories': photos,
            'sources':[{k:v for k,v in result.items() if k!='rows'} for result in results],
            'fetched_at':datetime.now().astimezone().isoformat(),'method':'official_headline_index',
            'notice':'快讯仅含公开标题、栏目日期与链接；图片报道另核对原文配图。不存储全文或图片，不是AI摘要，也不是你的大棚监测记录。'}
        _expires=time.monotonic()+(3600 if all(r['status']=='ok' for r in results) else 60)
        return _cache
