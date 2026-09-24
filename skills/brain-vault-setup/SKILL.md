---
name: brain-vault-setup
description: Set up Brain Vault for the user end to end — the Chrome extension that saves links, tweets, articles and screenshots with a note, sorts them with Jev, and publishes them to the user's own GitHub Pages site. Clones the extension, creates the user's vault repo on GitHub, turns on Pages, configures and starts the local helper so it runs at every login, and walks them through adding the extension to Chrome. Use when the user asks to install, set up, or get started with Brain Vault, make their own vault, or fix a Brain Vault install that isn't saving or publishing.
---

# Set up Brain Vault

Brain Vault has three parts, and the user needs all three:

1. **The extension code** — `github.com/samyakjain0606/brain-vault-extension` (extension, local helper, site template).
2. **Their vault repo** — a GitHub repo of their own that holds `vault.json` and the site, published with GitHub Pages.
3. **The helper** — `bridge/server.py`, a small stdlib Python server on `localhost:5128` that the extension talks to. It sorts each save with Jev and pushes the vault to GitHub.

Work through the steps in order. Run the commands yourself; only stop for the things that genuinely need the user (the questions in step 2, signing in to GitHub, and clicking in Chrome). Keep the user posted in one short line per step.

## 1. Check the machine

```sh
uname -s; git --version; python3 -c 'import sys; print(sys.version.split()[0])'; gh --version | head -1; gh auth status
```

- **OS.** macOS and Linux are supported. On Windows, point the user to the manual steps in the repo README and stop.
- **Python 3.9 or newer** is required. No packages are needed.
- **GitHub CLI.** If `gh` is missing, install it (`brew install gh` on macOS; on Linux follow https://github.com/cli/cli#installation). If it isn't signed in, ask the user to run `! gh auth login` in this session (it's interactive, so they must run it themselves). Then run `gh auth setup-git` so pushes from the helper work without prompts.
- **Chrome** (or another Chromium browser such as Arc, Brave or Edge) is needed for the extension.

Get their GitHub login and name for later: `gh api user --jq '.login, .name'`.

If `curl -fs localhost:5128/health` already answers, a helper is running. Show the user what it reports (vault folder, whether Jev is on) and ask whether they want to fix that install or start fresh before going on.

## 2. Ask the user (once, together)

Ask these in a single question round, with the defaults filled in:

- **Name on the site**: default from `gh api user` (first name for the greeting, full name next to the photo).
- **Vault repo name**: default `brain-vault`. The site will be at `https://<login>.github.io/<repo>/`. (A repo named `<login>.github.io` publishes at the root.)
- **Public is OK?** GitHub Pages on a free account needs a **public** repo, so every save, note and screenshot will be public. Make sure they're fine with that. If they have GitHub Pro/Team they can use a private repo, but the site itself is still public.
- **TypeSafe API key** for Jev, from https://console.typesafe.ai. They can paste it here (you'll write it to a local file and never print it back), or skip it and add it later. Without it, Brain Vault still works and sorts with simple keyword rules.

Folders: the extension goes in `~/brain-vault-extension` and the vault in `~/<repo>` unless the user says otherwise. Below, `EXT` and `VAULT` mean those paths, `LOGIN` and `REPO` mean their GitHub login and repo name.

## 3. Get the extension code

- If the current directory is already a clone (it has `manifest.json` and `bridge/server.py`), use it as `EXT`.
- If `EXT` exists and is a clone, update it: `git -C EXT pull --ff-only`.
- Otherwise: `git clone https://github.com/samyakjain0606/brain-vault-extension EXT`.

## 4. Create the vault repo

First check it doesn't exist: `gh repo view LOGIN/REPO`. If it does, ask whether to use it (clone it to `VAULT` and skip to the Pages step) or pick another name. Never overwrite an existing repo or folder.

```sh
mkdir -p VAULT && cd VAULT && git init -b main
cp EXT/site/index.html EXT/site/favicon.png .
```

Edit the `window.BRAIN_VAULT` block near the top of `VAULT/index.html` (use your file-edit tool, not sed):

- `owner`: their first name
- `fullName`: their full name
- `github`: `LOGIN`
- `about`: keep the default line, or use a sentence or two from the user if they gave one
- leave `extensionRepo` as it is, so their site links back to the extension

Then commit and publish:

```sh
cd VAULT && git add -A && git commit -m "Start my Brain Vault"
gh repo create REPO --public --source . --remote origin --push --description "My Brain Vault: links, reads and inspiration, sorted."
git -C VAULT remote set-url origin https://github.com/LOGIN/REPO.git   # https so the helper can push via gh's credentials
```

Use `--private` instead of `--public` only if the user chose that in step 2.

Turn on GitHub Pages from `main`:

```sh
gh api -X POST repos/LOGIN/REPO/pages -f 'source[branch]=main' -f 'source[path]=/'
```

A 409 means Pages is already on, which is fine. A 422 on a private repo means their plan doesn't include Pages for private repos: tell them, and offer to make the repo public (`gh repo edit LOGIN/REPO --visibility public --accept-visibility-change-consequences`) only if they agree.

## 5. Configure the helper

Create `EXT/bridge/.env` from `EXT/bridge/.env.example`, with:

```
TYPESAFE_API_KEY=<their key, or empty>
BRAIN_VAULT_DIR=<VAULT>
```

Then `chmod 600 EXT/bridge/.env`. Never echo the key, never commit this file (it's already in `.gitignore`), and don't put the key in any command line.

## 6. Start the helper, and keep it running

```sh
EXT/bridge/install-service.sh
```

This installs a LaunchAgent (macOS) or systemd user service (Linux) that starts the helper now and at every login, and restarts it if it crashes. It prints `Helper is running on http://localhost:5128` when it's up. If it fails, read `EXT/bridge/server.log`, fix the cause, and run it again.

Check it: `curl -s localhost:5128/health`. `vault` must be `VAULT`, and `jev` must be `true` if they gave a key.

If the service can't be installed (no systemd, for example), start it with `nohup python3 EXT/bridge/server.py >> EXT/bridge/server.log 2>&1 &` and tell the user it won't survive a restart.

## 7. Add the extension to Chrome

This needs the user's hands. Chrome doesn't allow installing unpacked extensions from the command line.

On macOS, copy the folder path and open the extensions page for them:

```sh
printf '%s' "EXT" | pbcopy
open -a "Google Chrome" "chrome://extensions"
```

Then tell them exactly this:

1. Turn on **Developer mode** (top right).
2. Click **Load unpacked**.
3. Press **⌘⇧G**, paste (the folder path is on the clipboard), press Return, then click **Select**.
4. Pin Brain Vault from the puzzle-piece menu so the icon is always there.

On Linux, give the same steps with the full `EXT` path to pick. Wait for them to confirm it's loaded. The panel footer shows "Helper running" when it can reach `localhost:5128`, and "Helper off" when it can't.

## 8. First save

Ask for a link they'd like to keep (or offer one) and a line on why. Save it through the helper so the whole path is tested:

```sh
curl -s -X POST localhost:5128/save -H 'Content-Type: application/json' \
  -d '{"url": "<link>", "note": "<why>", "pushToGithub": true}'
```

Check the response: `item.shelf`, `item.topic` and `item.tags` show how Jev sorted it, `item.classifiedBy` is `jev` when the key works, and `pushed` must be `true`. If `pushError` is set, fix it (usually `gh auth setup-git`, or the remote not being https) and save again.

Pages takes a minute or two to build the first time. Check with `gh api repos/LOGIN/REPO/pages/builds/latest --jq .status` until it says `built`, then open `https://LOGIN.github.io/REPO/` (or tell them the link).

## 9. Wrap up

Tell the user, briefly:

- Their site: `https://LOGIN.github.io/REPO/`, and their vault repo.
- How to save: click the Brain Vault icon or press **⌘⇧S** on any tab, write why, pick a shelf or leave it on Auto. On the Inspiration shelf it captures a screenshot, and *Select area* grabs just part of the page. Right-click any link to save it without opening it.
- Keep **Publish to GitHub** on in the panel footer for saves to go live.
- The helper runs by itself now. `EXT/bridge/install-service.sh status` checks it, and `uninstall` removes it.
- To change the shelves, topics or tags, edit `EXT/bridge/taxonomy.py`, then re-sort everything with `python3 EXT/bridge/migrate.py --reclassify`.

## If something is off later

| Symptom | Check |
| --- | --- |
| Panel footer says "Helper off" | `EXT/bridge/install-service.sh status`; read `EXT/bridge/server.log` |
| Saves work but don't appear on the site | Publish to GitHub switch on; `git -C VAULT status` and `git -C VAULT push` for the real error; Pages build status |
| Everything sorted by keywords, not Jev | `curl -s localhost:5128/health` shows `"jev": false`: the key is missing from `EXT/bridge/.env`, then rerun `install-service.sh` so the helper reloads it |
| Wrong vault folder | `BRAIN_VAULT_DIR` in `EXT/bridge/.env`, then rerun `install-service.sh` |
