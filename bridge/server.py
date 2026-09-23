#!/usr/bin/env python3
"""
Brain Vault helper.

The Chrome extension POSTs links here. The helper reads the page, sorts it with Jev
(TypeSafe System One), writes it to vault.json, regenerates the Markdown mirror, and
optionally pushes the vault to GitHub (which serves the site via GitHub Pages).

Usage:
    python3 server.py

Settings (env vars or bridge/.env): BRAIN_VAULT_DIR, BRAIN_VAULT_PORT, TYPESAFE_API_KEY.
"""

import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import jev  # noqa: E402
import vault  # noqa: E402
from config import PORT, VAULT_DIR  # noqa: E402
from pipeline import SHOT_TYPES, SHOTS_DIR, build_item, save_screenshot  # noqa: E402

MAX_BODY = 12 * 1024 * 1024


def git_push(message):
    """Commit and push the vault folder. Returns (pushed, error)."""
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")

    def run(*args):
        return subprocess.run(["git", *args], capture_output=True, text=True, timeout=45, cwd=VAULT_DIR, env=env)

    try:
        if run("rev-parse", "--is-inside-work-tree").returncode != 0:
            return False, f"{VAULT_DIR} is not a git repo. Run: git init && git remote add origin <your-repo-url>"
        run("add", "-A")
        commit = run("commit", "-m", message[:72])
        if commit.returncode != 0 and "nothing to commit" not in commit.stdout:
            return False, f"Commit failed: {commit.stderr.strip()}"
        push = run("push")
        if push.returncode != 0:
            return False, f"Push failed: {push.stderr.strip()}"
        return True, None
    except subprocess.TimeoutExpired:
        return False, "Git timed out"
    except FileNotFoundError:
        return False, "git is not installed"


class Handler(BaseHTTPRequestHandler):
    # ---- routing ----

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/health":
            self._json(200, {
                "status": "ok",
                "vault": VAULT_DIR,
                "jev": jev.enabled(),
                "items": len(vault.load()["items"]),
            })
        elif path == "/items":
            self._json(200, {"items": vault.load()["items"]})
        elif path.startswith("/shots/"):
            self._serve_shot(path[len("/shots/"):])
        else:
            self._json(404, {"error": "Not found"})

    def do_POST(self):
        path = self.path.split("?")[0]
        body = self._body()
        if body is None:
            return
        if path == "/save":
            self._save(body)
        elif path == "/bookmark":  # older extension builds
            self._save({**body, "kind": body.get("kind") or "tool", "title": body.get("name", "")})
        elif path in ("/item/delete", "/bookmark/delete"):
            self._delete(body)
        else:
            self._json(404, {"error": "Not found"})

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    # ---- handlers ----

    def _save(self, body):
        url = (body.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            self._json(400, {"error": "That doesn’t look like a web link."})
            return

        screenshot = save_screenshot(body["screenshot"], url) if body.get("screenshot") else ""
        item, info = build_item(
            url,
            note=body.get("note", ""),
            kind=body.get("kind", "auto"),
            title=body.get("title", ""),
            image=body.get("image", ""),
            screenshot=screenshot,
        )
        item, updated = vault.upsert(item)
        print(f"[save] {'Updated' if updated else 'Saved'}: {item['title']} → {item['shelf']}/{item['topic']} "
              f"tags={item['tags']} by={item['classifiedBy']}")

        resp = {"item": item, "updated": updated, "pushed": False}
        if info.get("jevError"):
            resp["jevError"] = info["jevError"]
        if body.get("pushToGithub"):
            pushed, err = git_push(f"vault: {item['title'][:60]}")
            resp["pushed"] = pushed
            if err:
                resp["pushError"] = err
                print(f"[git] {err}")
        self._json(200, resp)

    def _delete(self, body):
        item_id = (body.get("id") or "").strip()
        if not item_id:
            self._json(400, {"error": "No id given"})
        elif vault.delete(item_id):
            self._json(200, {"deleted": item_id})
        else:
            self._json(404, {"error": "Not in the vault"})

    def _serve_shot(self, name):
        name = os.path.basename(name)
        path = os.path.join(SHOTS_DIR, name)
        types = {v: k for k, v in SHOT_TYPES.items()}
        ext = name.rsplit(".", 1)[-1].lower()
        if ext not in types or not os.path.isfile(path):
            self._json(404, {"error": "Not found"})
            return
        with open(path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", types[ext])
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "max-age=86400")
        self.end_headers()
        self.wfile.write(data)

    # ---- plumbing ----

    def _body(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > MAX_BODY:
                self._json(413, {"error": "Request too large"})
                return None
            return json.loads(self.rfile.read(length) or b"{}")
        except Exception as e:
            self._json(400, {"error": f"Bad request: {e}"})
            return None

    def _json(self, code, data):
        try:
            payload = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(code)
            self._cors()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except BrokenPipeError:
            pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, fmt, *args):
        print(f"[http] {args[0]}")


def main():
    os.makedirs(VAULT_DIR, exist_ok=True)
    print("Brain Vault helper")
    print(f"  Vault: {VAULT_DIR}")
    print(f"  Jev:   {'on' if jev.enabled() else 'off (set TYPESAFE_API_KEY to sort with Jev)'}")
    print(f"  URL:   http://localhost:{PORT}\n", flush=True)
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
