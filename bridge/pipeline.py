"""
Turn a saved link into a vault item: read the page, apply URL facts, ask Jev, decide.
Used by the helper (server.py) and by migrate.py.
"""

import base64
import hashlib
import os
import re
from datetime import date

import jev
from config import SHELF_CONFIDENCE_FLOOR, VAULT_DIR
from enrich import clean_title, fetch_page, fetch_tweet, guess_type, host_of, source_name

SHOTS_DIR = os.path.join(VAULT_DIR, "shots")
MAX_SHOT_BYTES = 8 * 1024 * 1024
SHOT_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}

# Used only when Jev isn't configured: rough keyword rules so saves still get a topic.
FALLBACK_TOPICS = [
    ("ai", r"\b(ai|llm|gpt|claude|agent|agents|prompt|model|openai|anthropic|machine learning)\b"),
    ("design", r"\b(design|ui|ux|icon|icons|svg|font|typography|animation|figma|illustration|mockup)\b"),
    ("engineering", r"\b(code|coding|github|api|programming|developer|software|javascript|python|rust)\b"),
    ("startups", r"\b(startup|founder|founders|brand|marketing|growth|product|yc)\b"),
    ("writing", r"\b(writing|writer|copywriting|content|newsletter)\b"),
    ("money", r"\b(invest|investing|stock|stocks|finance|market|economy)\b"),
    ("craft", r"\b(work|learning|productivity|career|habit|great work)\b"),
]


def item_id(url):
    return hashlib.sha1(url.encode()).hexdigest()[:10]


def save_screenshot(data_url, url):
    """Write a data:image/... URL into shots/ and return its path relative to the vault."""
    m = re.match(r"^data:(image/[a-z]+);base64,(.+)$", data_url or "", re.S)
    if not m or m.group(1) not in SHOT_TYPES:
        return ""
    raw = base64.b64decode(m.group(2), validate=False)
    if not raw or len(raw) > MAX_SHOT_BYTES:
        return ""
    os.makedirs(SHOTS_DIR, exist_ok=True)
    digest = hashlib.sha1(url.encode() + raw[:4096]).hexdigest()[:8]
    name = f"{date.today().isoformat()}-{digest}.{SHOT_TYPES[m.group(1)]}"
    with open(os.path.join(SHOTS_DIR, name), "wb") as f:
        f.write(raw)
    return f"shots/{name}"


def _structural(url_type):
    return {"tweet": "post", "x-article": "reading-x", "repo": "tool"}.get(url_type)


def _fallback_topic(text):
    text = text.lower()
    for key, pattern in FALLBACK_TOPICS:
        if re.search(pattern, text):
            return key
    return "other"


def build_item(url, note="", kind="auto", title="", image="", screenshot="", saved_at=None, prefetched=None):
    """
    Returns (item, info). `info` carries non-stored details such as a Jev error.
    `prefetched` lets migrate.py pass already-known title/description to skip refetching.
    """
    url = url.strip()
    url_type = guess_type(url, default="article")
    item = {
        "id": item_id(url),
        "url": url,
        "type": url_type,
        "title": "",
        "description": "",
        "note": (note or "").strip(),
        "source": source_name(url),
        "host": host_of(url),
        "image": image or "",
        "screenshot": screenshot or "",
        "savedAt": saved_at or date.today().isoformat(),
    }
    info = {}

    # 1. Read the page (or the tweet).
    text = ""
    if url_type == "tweet":
        tw = fetch_tweet(url)
        item.update({k: v for k, v in tw.items() if v})
        text = tw.get("text", "")
        if re.fullmatch(r"https://t\.co/\w+", text.strip()):
            # A tweet that is only a link is how X embeds its long-form Articles.
            url_type = item["type"] = "x-article"
            item.pop("text", None)
            text = ""
        item["title"] = clean_title(title, url) or (text.split("\n")[0][:90] if text else f"Post by @{tw.get('handle', '')}")
    else:
        page = prefetched if prefetched is not None else fetch_page(url)
        item["title"] = clean_title(title, url) or clean_title(page.get("title"), url) or host_of(url)
        item["description"] = (page.get("description") or "")[:280]
        item["image"] = item["image"] or page.get("image", "")
        text = page.get("snippet", "")

    # 2. Ask Jev.
    result = None
    if jev.enabled():
        try:
            result = jev.classify({
                "url": url, "host": item["host"], "title": item["title"],
                "description": item["description"], "text": text, "note": item["note"],
            })
        except jev.JevError as e:
            info["jevError"] = str(e)
            print(f"[jev] {e}")

    # 3. Decide.
    shelf, shelf_source = jev.resolve_shelf(_structural(url_type), kind, result)
    item["shelf"] = shelf
    if result:
        item["topic"] = result["topic"] or "other"
        item["tags"] = result["tags"]
        item["classifiedBy"] = "jev"
        item["needsReview"] = shelf_source == "jev" and result["shelfConfidence"] < SHELF_CONFIDENCE_FLOOR
        item["jev"] = result["jev"]
    else:
        item["topic"] = _fallback_topic(" ".join([item["title"], item["description"], item["note"], text[:500]]))
        item["tags"] = []
        item["classifiedBy"] = "rules"
        item["needsReview"] = False
    item["shelfSource"] = shelf_source
    return item, info
