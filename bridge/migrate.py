#!/usr/bin/env python3
"""
Build or refresh vault.json.

    python3 migrate.py                 # import legacy data.json + bookmarks.json into vault.json
    python3 migrate.py --reclassify    # re-sort every item (e.g. after adding a Jev key)
    python3 migrate.py --dry-run       # show what would happen, write nothing

Keeps original save dates, notes and screenshots. Safe to re-run.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import jev  # noqa: E402
import vault  # noqa: E402
from config import VAULT_DIR  # noqa: E402
from pipeline import build_item  # noqa: E402


def legacy_records():
    """Yield (url, fields) from the pre-2.0 data.json and bookmarks.json."""
    path = os.path.join(VAULT_DIR, "data.json")
    if os.path.exists(path):
        for a in json.load(open(path)).get("articles", []):
            yield a["url"], {"title": a.get("title", ""), "note": a.get("note", ""), "savedAt": a.get("date"),
                             "kind": a.get("kind") or "auto", "image": a.get("image", ""), "screenshot": a.get("screenshot", "")}
    path = os.path.join(VAULT_DIR, "bookmarks.json")
    if os.path.exists(path):
        for b in json.load(open(path)).get("bookmarks", []):
            name = b.get("name", "").strip()
            note = b.get("note", "")
            # Old builds had no note field, so a short lowercase "name" like "cool svgs" was really a note.
            if name and not note and name == name.lower() and len(name.split()) <= 4 and "." not in name:
                name, note = "", name
            yield b["url"], {"title": "" if name.startswith("http") else name, "note": note,
                             "savedAt": b.get("date"), "kind": "tool", "image": "", "screenshot": "", "legacy": True}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reclassify", action="store_true", help="re-sort items already in vault.json")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    print(f"Vault: {VAULT_DIR}   Jev: {'on' if jev.enabled() else 'off (keyword rules only)'}\n")
    if args.reclassify and not jev.enabled():
        print("--reclassify needs Jev. Set TYPESAFE_API_KEY (env or bridge/.env) first.")
        return
    current = {i["url"]: i for i in vault.load()["items"]}
    todo = {}

    for url, fields in legacy_records():
        if url not in current and url not in todo:
            todo[url] = fields
    if args.reclassify:
        for url, i in current.items():
            # Keep the user's explicit shelf choice; everything else is re-judged.
            kind = i["shelf"] if i.get("shelfSource") == "user" else "auto"
            todo[url] = {"title": i.get("title", ""), "note": i.get("note", ""), "savedAt": i.get("savedAt"),
                         "kind": kind, "image": i.get("image", ""), "screenshot": i.get("screenshot", "")}

    if not todo:
        print("Nothing to do.")
        return

    items = dict(current)
    for n, (url, f) in enumerate(todo.items(), 1):
        item, info = build_item(url, note=f["note"], kind=f["kind"], title=f["title"], image=f["image"],
                                screenshot=f["screenshot"], saved_at=f["savedAt"])
        if f.get("legacy"):
            item["shelfSource"] = "legacy"  # old "Sites" tab, not a deliberate shelf choice
        items[url] = item
        flag = "  (review)" if item.get("needsReview") else ""
        err = f"  [jev error: {info['jevError']}]" if info.get("jevError") else ""
        print(f"[{n}/{len(todo)}] {item['shelf']:<11} {item['topic']:<11} {', '.join(item['tags']) or '-':<34} "
              f"{item['title'][:48]}{flag}{err}")

    if args.dry_run:
        print("\nDry run: nothing written.")
        return
    vault.replace_all(list(items.values()))
    print(f"\nWrote {len(items)} items to {vault.VAULT_PATH}")


if __name__ == "__main__":
    main()
