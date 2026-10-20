"""Bounded public HTTP fetcher: validate redirects and pin DNS at connection time."""
import ipaddress
import socket
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
import httpx
from app.services.errors import ServiceError

def public_url(url, resolve=True):
    try:
        p = urlsplit(url)
        if p.scheme not in {"http", "https"} or not p.hostname or p.username or p.password or p.port not in (None, 80, 443):
            raise ValueError()
        host = p.hostname.lower()
        if host in {"localhost", "metadata.google.internal"} or host.endswith((".local", ".internal", ".localhost")): raise ValueError()
        try:
            addresses = [ipaddress.ip_address(host)]
        except ValueError:
            addresses = [ipaddress.ip_address(i[4][0]) for i in socket.getaddrinfo(host, p.port or (443 if p.scheme == "https" else 80), type=socket.SOCK_STREAM)] if resolve else []
        if any(not a.is_global for a in addresses): raise ValueError()
        if resolve and not addresses: raise ValueError()
        return p, str(addresses[0]) if addresses else None
    except (ValueError, OSError) as exc:
        raise ServiceError(422, "仅支持可访问的公网HTTP/HTTPS地址，不允许本地网络、凭据或非标准端口") from exc

def canonical(url):
    p, _ = public_url(url, resolve=False)
    query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}]
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path or "/", urlencode(sorted(query)), ""))

class PinnedTransport(httpx.HTTPTransport):
    def handle_request(self, request):
        p, address = public_url(str(request.url))
        request.headers["Host"] = p.netloc
        request.extensions["sni_hostname"] = p.hostname
        request.url = request.url.copy_with(host=address)
        return super().handle_request(request)

def fetch(url, headers=None, limit=2_000_000, timeout=12, validate_url=None):
    with httpx.Client(transport=PinnedTransport(), timeout=timeout, follow_redirects=False, trust_env=False) as client:
        for _ in range(4):
            if validate_url:
                validate_url(url)
            public_url(url)
            with client.stream("GET", url, headers={"User-Agent": "PengzhiNews/2.0 (+agriculture research reader)", **(headers or {})}) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    url = urljoin(url, response.headers.get("location", "")); continue
                if response.status_code == 304: return b"", dict(response.headers), url, 304
                response.raise_for_status()
                content = bytearray()
                for chunk in response.iter_bytes():
                    content.extend(chunk)
                    if len(content) > limit: raise ServiceError(413, "来源响应超过大小限制")
                return bytes(content), dict(response.headers), url, response.status_code
    raise ServiceError(422, "来源重定向次数过多")
