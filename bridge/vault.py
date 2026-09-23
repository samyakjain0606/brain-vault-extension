"""
vault.json — the single source of truth for Brain Vault.

Everything else (index.md, per-topic Markdown files, the website) is generated from it.
"""

import json
import os
import threading
from datetime import datetime

from config import VAULT_DIR
from taxonomy import SHELVES, TOPICS

VAULT_PATH = os.path.join(VAULT_DIR, "vault.json")
_lock = threading.Lock()


def load():
    if not os.path.exists(VAULT_PATH):
        return {"version": 1, "updatedAt": None, "items": []}
    with open(VAULT_PATH) as f:
        return json.load(f)


def _write(data):
    data["updatedAt"] = datetime.now().isoformat(timespec="seconds")
    data["items"].sort(key=lambda i: i.get("savedAt") or "", reverse=True)
    tmp = VAULT_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, VAULT_PATH)
    render_markdown(data["items"])


def find(url):
    return next((i for i in load()["items"] if i["url"] == url), None)


def upsert(item):
    """Insert a new item, or merge into the existing one with the same URL."""
    with _lock:
        data = load()
        existing = next((i for i in data["items"] if i["url"] == item["url"]), None)
        if existing:
            # Keep the original save date and any note the user wrote before.
            item["savedAt"] = existing.get("savedAt") or item.get("savedAt")
            if not item.get("note") and existing.get("note"):
                item["note"] = existing["note"]
            if not item.get("screenshot") and existing.get("screenshot"):
                item["screenshot"] = existing["screenshot"]
            existing.clear()
            existing.update(item)
        else:
            data["items"].append(item)
        _write(data)
        return item, bool(existing)


def delete(item_id):
    with _lock:
        data = load()
        before = len(data["items"])
        data["items"] = [i for i in data["items"] if i.get("id") != item_id]
        if len(data["items"]) == before:
            return False
        _write(data)
        return True


def replace_all(items):
    with _lock:
        data = load()
        data["items"] = items
        _write(data)


# ---- Markdown mirror (readable on GitHub without the site) ----

def _fmt_date(iso):
    try:
        return datetime.fromisoformat(iso).strftime("%-d %b %Y")
    except Exception:
        return iso or ""


def _cell(text):
    return (text or "").replace("|", "\\|").replace("\n", " ").strip()


def render_markdown(items):
    topic_names = {k: v["name"] for k, v in TOPICS.items()}
    lines = [
        "# Brain Vault",
        "",
        f"{len(items)} things worth keeping. Browse them on the site, or here.",
        "",
        "| Saved | Title | Shelf | Topic | Note |",
        "|-------|-------|-------|-------|------|",
    ]
    for i in items:
        lines.append(
            f"| {_fmt_date(i.get('savedAt'))} | [{_cell(i.get('title') or i['url'])}]({i['url']}) "
            f"| {SHELVES.get(i.get('shelf'), {}).get('name', '')} | {topic_names.get(i.get('topic'), '')} "
            f"| {_cell(i.get('note'))} |"
        )
    with open(os.path.join(VAULT_DIR, "index.md"), "w") as f:
        f.write("\n".join(lines) + "\n")

    topics_dir = os.path.join(VAULT_DIR, "topics")
    os.makedirs(topics_dir, exist_ok=True)
    for key, name in topic_names.items():
        group = [i for i in items if i.get("topic") == key]
        path = os.path.join(topics_dir, f"{key}.md")
        if not group:
            if os.path.exists(path):
                os.remove(path)
            continue
        out = [f"# {name}", ""]
        for i in group:
            out.append(f"### [{i.get('title') or i['url']}]({i['url']})")
            if i.get("description"):
                out.append(f"> {i['description']}")
            meta = [SHELVES.get(i.get("shelf"), {}).get("name", ""), i.get("source", ""), _fmt_date(i.get("savedAt"))]
            out.append("")
            out.append(" · ".join(m for m in meta if m))
            if i.get("tags"):
                out.append("Tags: " + ", ".join(i["tags"]))
            if i.get("note"):
                out.append(f"\n**Note:** {i['note']}")
            out.append("\n---\n")
        with open(path, "w") as f:
            f.write("\n".join(out))
