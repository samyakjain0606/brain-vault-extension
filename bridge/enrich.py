"""
Metadata helpers shared by server.py and migrate.py.
Fetches og:title / og:description / og:image, and tweet text via X's public oEmbed endpoint.
"""

import hashlib
import html
import html.parser
import json
import re
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"

FRIENDLY_SOURCES = {
    "news.ycombinator.com": "Hacker News",
    "reddit.com": "Reddit",
    "twitter.com": "X",
    "x.com": "X",
    "medium.com": "Medium",
    "dev.to": "DEV",
    "github.com": "GitHub",
    "youtube.com": "YouTube",
    "youtu.be": "YouTube",
    "arxiv.org": "arXiv",
    "substack.com": "Substack",
}

TWEET_RE = re.compile(r"^https?://(www\.)?(x|twitter)\.com/([^/]+)/status/(\d+)")
X_ARTICLE_RE = re.compile(r"^https?://(www\.)?(x|twitter)\.com/(i/article|[^/]+/article)/")


def item_id(url):
    return hashlib.sha1(url.encode()).hexdigest()[:10]


def host_of(url):
    return (urllib.parse.urlparse(url).hostname or "").lower().removeprefix("www.")


def source_name(url):
    host = host_of(url)
    for domain, name in FRIENDLY_SOURCES.items():
        if host == domain or host.endswith("." + domain):
            return name
    return host or "unknown"


def guess_type(url, default="article"):
    """Cheap structural guess. Jev refines article/inspiration/tool later."""
    if X_ARTICLE_RE.match(url):
        return "x-article"
    if TWEET_RE.match(url):
        return "tweet"
    host = host_of(url)
    if host in ("youtube.com", "youtu.be", "vimeo.com"):
        return "video"
    if host == "github.com" and len(urllib.parse.urlparse(url).path.strip("/").split("/")) >= 2:
        return "repo"
    return default


class _MetaParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta, self.title, self.icon = {}, "", None
        self._in_title = False
        self.text, self._skip = [], 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta":
            key = (a.get("property") or a.get("name") or "").lower()
            if key and a.get("content") and key not in self.meta:
                self.meta[key] = a["content"].strip()
        elif tag == "title":
            self._in_title = True
        elif tag == "link" and "icon" in (a.get("rel") or "").lower() and not self.icon:
            self.icon = a.get("href")
        if tag in ("script", "style", "noscript", "svg", "nav", "footer", "header"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag in ("script", "style", "noscript", "svg", "nav", "footer", "header"):
            self._skip = max(0, self._skip - 1)

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._skip and data.strip():
            self.text.append(data.strip())


def _get(url, limit=300_000, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(limit).decode("utf-8", errors="ignore"), resp.geturl()


def fetch_page(url):
    """Return dict(title, description, image, snippet) — any may be empty."""
    try:
        body, final = _get(url)
    except Exception as e:
        print(f"  [warn] fetch failed: {e}")
        return {}
    p = _MetaParser()
    try:
        p.feed(body)
    except Exception:
        pass
    m = p.meta
    image = m.get("og:image") or m.get("twitter:image") or ""
    if image:
        image = urllib.parse.urljoin(final, image)
    return {
        "title": html.unescape(m.get("og:title") or p.title).strip(),
        "description": html.unescape(m.get("og:description") or m.get("description") or "").strip(),
        "image": image,
        "snippet": " ".join(p.text)[:2000],
    }


def fetch_tweet(url):
    """X oEmbed: no auth, returns author + tweet text."""
    api = "https://publish.twitter.com/oembed?omit_script=1&dnt=1&url=" + urllib.parse.quote(url, safe="")
    try:
        body, _ = _get(api, timeout=8)
        data = json.loads(body)
    except Exception as e:
        print(f"  [warn] oembed failed: {e}")
        return {}
    m = re.search(r"<p[^>]*>(.*?)</p>", data.get("html", ""), re.S)
    text = ""
    if m:
        text = re.sub(r"<br\s*/?>", "\n", m.group(1))
        text = html.unescape(re.sub(r"<[^>]+>", "", text)).strip()
    handle = urllib.parse.urlparse(data.get("author_url", "")).path.strip("/")
    return {"author": data.get("author_name", ""), "handle": handle, "text": text}


def clean_title(title, url):
    """Strip site-name suffixes like 'Foo — Bar | Site' and GitHub boilerplate."""
    t = (title or "").strip()
    if not t or t.startswith("http"):
        return ""
    if host_of(url) == "github.com":
        t = re.sub(r"^GitHub - ", "", t)
        t = re.sub(r" · GitHub$", "", t)
        t = t.split(": ", 1)[0] if ": " in t else t
    t = re.sub(r"\s+[|·–—-]\s+[^|·–—-]{2,30}$", "", t) if len(t) > 40 else t
    return t.strip()


def enrich(item):
    """Fill missing fields in place. Never overwrites a non-empty user field."""
    url = item["url"]
    if item.get("type") == "tweet":
        tw = fetch_tweet(url)
        item.setdefault("author", tw.get("author", ""))
        item.setdefault("handle", tw.get("handle", ""))
        if tw.get("text"):
            item["text"] = tw["text"]
        if not item.get("title") and tw.get("text"):
            item["title"] = tw["text"].split("\n")[0][:90]
        return item

    page = fetch_page(url)
    title = clean_title(item.get("title"), url) or clean_title(page.get("title"), url)
    item["title"] = title or host_of(url)
    if not item.get("description") and page.get("description"):
        item["description"] = page["description"][:280]
    if not item.get("image") and page.get("image"):
        item["image"] = page["image"]
    item["_snippet"] = page.get("snippet", "")
    return item
