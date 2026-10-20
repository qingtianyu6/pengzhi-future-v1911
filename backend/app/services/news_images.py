"""Discover article image URLs; never store or proxy remote image files or article text."""
from collections import OrderedDict
from datetime import UTC, datetime
from html.parser import HTMLParser
import re
import threading
import time
from urllib.parse import urljoin, urlsplit
from app.services import content_network
from app.services.errors import ServiceError

_cache = OrderedDict()
_inflight = {}
_lock = threading.Lock()
_VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}
_CONTENT = re.compile(r'trs_editor|trs_ueditor|trs_preappend|custom_unionstyle|arc_body|ucap-content|article[-_]?content|article[-_]?body', re.I)
_DECORATION = re.compile(r'(?:logo|qrcode|qr-code|weixin|wechat|icon|loading|spacer|bajgwa|jiucuo|gonotgov|/images/red\.|二维码|公众号|扫一扫)', re.I)

def official_article(url):
    parsed, _ = content_network.public_url(url, resolve=False)
    prefix = {'www.moa.gov.cn': ('/xw/qg/', '/xw/zwdt/'), 'zzys.moa.gov.cn': ('/gdxw/',)}.get(parsed.hostname, ())
    if not prefix or not parsed.path.startswith(prefix) or not re.fullmatch(r'.*/t\d{8}_\d+\.htm', parsed.path):
        raise ServiceError(422, '公开配图仅支持当前官方资讯的原文地址')
    return content_network.canonical(url)

def safe_image(value, base):
    try:
        if not value or not value.strip() or value.strip().startswith(('#', '?')):
            return None
        url = urljoin(base, value.strip())
        parsed, _ = content_network.public_url(url, resolve=False)
        if len(url) > 2048 or _DECORATION.search(parsed.path) or parsed.path.lower().endswith('.svg'):
            return None
        return url
    except (ServiceError, ValueError):
        return None

class ArticleImages(HTMLParser):
    def __init__(self, base):
        super().__init__(convert_charrefs=True)
        self.base = base; self.stack = []; self.body = []; self.meta = []

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        marker = (attrs.get('class') or '') + ' ' + (attrs.get('id') or '')
        blocked = tag in {'header', 'footer', 'nav', 'script', 'style', 'aside'} or bool(_DECORATION.search(marker)) or any(b for _, _, b in self.stack)
        content = tag == 'article' or bool(_CONTENT.search(marker)) or any(c for _, c, _ in self.stack)
        if tag == 'meta' and (attrs.get('property') or attrs.get('name', '')).lower() in {'og:image', 'og:image:url', 'twitter:image', 'twitter:image:src'}:
            value = safe_image(attrs.get('content', ''), self.base)
            if attrs.get('content') and value: self.meta.append((value, 'page_image_metadata', ''))
        if tag == 'img' and content and not blocked:
            tiny = any(re.fullmatch(r'\d+(?:px)?', attrs.get(key) or '') and int(attrs[key].removesuffix('px')) < 100 for key in ('width', 'height'))
            decoration = _DECORATION.search((attrs.get('alt') or '') + ' ' + marker)
            if not tiny and not decoration:
                values = [attrs.get(key) for key in ('data-original', 'data-src', 'data-lazy-src', 'src')]
                values += [candidate.strip().split()[0] for candidate in (attrs.get('data-srcset') or attrs.get('srcset') or '').split(',') if candidate.strip()]
                for value in values:
                    image = safe_image(value, self.base)
                    if image:
                        self.body.append((image, 'article_body', (attrs.get('alt') or '')[:200]))
                        break
        if tag not in _VOID: self.stack.append((tag, content, blocked))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]; break

def extract(raw, base):
    charset = re.search(br'charset\s*=\s*["\']?([\w-]+)', raw[:4096], re.I)
    encoding = charset[1].decode('ascii') if charset else 'utf-8'
    try: text = raw.decode(encoding, errors='replace')
    except LookupError: text = raw.decode('utf-8', errors='replace')
    parser = ArticleImages(base); parser.feed(text)
    return next(iter(parser.body or parser.meta), None)

def article_image(url, *, official=False):
    url = official_article(url) if official else content_network.canonical(url)
    key = (official, url)
    with _lock:
        cached = _cache.get(key)
        if cached and cached[0] > time.monotonic():
            _cache.move_to_end(key); return dict(cached[1])
        event = _inflight.get(key)
        owner = event is None
        if owner: event = _inflight.setdefault(key, threading.Event())
    if not owner:
        event.wait(20)
        with _lock:
            cached = _cache.get(key)
            if cached and cached[0] > time.monotonic(): return dict(cached[1])
        return {'status': 'unavailable', 'image_url': None, 'article_url': url}
    result = {'status': 'no_image', 'image_url': None, 'article_url': url, 'checked_at': datetime.now(UTC).isoformat()}
    try:
        raw, headers, final, _ = content_network.fetch(url, limit=1_000_000, timeout=5, validate_url=official_article if official else None)
        if official: official_article(final)
        if headers.get('content-type') and 'html' not in headers['content-type'].lower():
            result['status'] = 'unsupported'
        else:
            found = extract(raw, final)
            if found:
                image, method, alt = found
                result.update(status='found', image_url=image, method=method, alt=alt, article_url=final)
    except Exception as exc:
        result.update(status='unavailable', error_type=type(exc).__name__)
    finally:
        with _lock:
            _cache[key] = (time.monotonic() + (60 if result['status'] == 'unavailable' else 3600), result)
            _cache.move_to_end(key)
            while len(_cache) > 256: _cache.popitem(last=False)
            _inflight.pop(key, None); event.set()
    return dict(result)
