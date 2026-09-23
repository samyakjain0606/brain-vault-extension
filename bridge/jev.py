"""
Sort a saved link with Jev (TypeSafe System One).

One request, all questions in parallel over the same state:
  - shelf : Choice  — reading / post / inspiration / tool
  - topic : Choice  — one of the distinct topics (with an "other" escape)
  - tag_* : Noul    — one yes/no per candidate tag; code keeps the confident ones

Code owns the facts (URL patterns, the user's explicit shelf); Jev only judges meaning.
"""

import json
import re
import urllib.error
import urllib.request

from config import JEV_MODEL, MAX_TAGS, SHELF_CONFIDENCE_FLOOR, TAG_THRESHOLD, TYPESAFE_API_KEY, TYPESAFE_URL
from taxonomy import SHELVES, TAGS, TOPICS


class JevError(Exception):
    pass


def enabled():
    return bool(TYPESAFE_API_KEY)


def _tag_id(tag):
    return "tag_" + re.sub(r"[^a-z0-9]+", "_", tag.lower()).strip("_")


def build_request(page):
    """page: dict with url, host, title, description, text, note."""
    state = {
        "saved_link": {
            "url": page.get("url", ""),
            "site": page.get("host", ""),
            "title": page.get("title", ""),
            "description": page.get("description", ""),
            "page_text_excerpt": (page.get("text") or "")[:1500],
        },
        "why_the_user_saved_it": page.get("note") or "(no note)",
    }
    questions = {
        "shelf": {
            "type": "choice",
            "instructions": (
                "The user saved `saved_link` to a personal library, and `why_the_user_saved_it` is their note. "
                "Which shelf does this saved link belong on? Judge what the user is keeping it for, using the note when present."
            ),
            "criteria": {k: v["jev"] for k, v in SHELVES.items()},
        },
        "topic": {
            "type": "choice",
            "instructions": "What is the main subject of `saved_link`? Pick the single closest topic.",
            "criteria": {k: v["jev"] for k, v in TOPICS.items()},
        },
    }
    for tag, meaning in TAGS.items():
        questions[_tag_id(tag)] = {
            "type": "noul",
            "instructions": f"Does this description clearly apply to `saved_link`: \"{meaning}\"",
            "criteria": {
                "true": "The link's title, description, excerpt or the user's note clearly matches the description.",
                "false": "It does not match, or only matches loosely.",
            },
        }
    return {"model": JEV_MODEL, "state": state, "questions": questions}


def call(body, timeout=20):
    if not TYPESAFE_API_KEY:
        raise JevError("TYPESAFE_API_KEY is not set")
    req = urllib.request.Request(
        TYPESAFE_URL,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {TYPESAFE_API_KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="ignore")[:300]
        raise JevError(f"Jev HTTP {e.code}: {detail}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise JevError(f"Could not reach Jev: {e}") from e


def interpret(response):
    """Turn raw answers into the fields Brain Vault stores."""
    answers = response.get("answers", {})
    shelf = answers.get("shelf", {})
    topic = answers.get("topic", {})
    tag_scores = {tag: answers.get(_tag_id(tag), {}).get("noul", 0.0) for tag in TAGS}
    tags = [t for t, p in sorted(tag_scores.items(), key=lambda kv: -kv[1]) if p >= TAG_THRESHOLD][:MAX_TAGS]
    return {
        "shelf": shelf.get("choice"),
        "shelfConfidence": round(shelf.get("confidence", 0.0), 3),
        "topic": topic.get("choice"),
        "topicConfidence": round(topic.get("confidence", 0.0), 3),
        "tags": tags,
        # Raw judgments kept so thresholds can change later without re-asking Jev.
        "jev": {
            "model": response.get("model"),
            "shelf": {k: round(v, 3) for k, v in shelf.get("probabilities", {}).items()},
            "topic": {k: round(v, 3) for k, v in topic.get("probabilities", {}).items()},
            "tags": {k: round(v, 3) for k, v in tag_scores.items()},
        },
    }


def classify(page):
    return interpret(call(build_request(page)))


def resolve_shelf(structural, user_kind, jev_result):
    """
    Decide the final shelf. Priority: the user's explicit choice, then hard facts
    from the URL, then Jev (if confident enough), then a safe default.
    Returns (shelf, source).
    """
    user_map = {"article": "reading", "reading": "reading", "post": "post", "inspiration": "inspiration", "tool": "tool"}
    if user_kind in user_map:
        return user_map[user_kind], "user"
    if structural in ("post", "reading-x"):
        return ("post" if structural == "post" else "reading"), "url"
    if jev_result and jev_result.get("shelf"):
        if jev_result["shelfConfidence"] >= SHELF_CONFIDENCE_FLOOR or structural is None:
            return jev_result["shelf"], "jev"
    if structural == "tool":
        return "tool", "url"
    return (jev_result or {}).get("shelf") or "reading", "default"
