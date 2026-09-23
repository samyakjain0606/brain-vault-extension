"""
Settings for the Brain Vault helper. Everything can be overridden with environment
variables or a bridge/.env file (KEY=value per line), so anyone can run their own vault.
"""

import os

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_dotenv(path):
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(os.path.join(_HERE, ".env"))

# Where the vault lives. Make this folder a git repo with GitHub Pages to publish it.
VAULT_DIR = os.path.expanduser(os.environ.get("BRAIN_VAULT_DIR", "~/articles"))
PORT = int(os.environ.get("BRAIN_VAULT_PORT", "5128"))

# Jev (TypeSafe System One) — sorts every save. Get a key at https://console.typesafe.ai
TYPESAFE_API_KEY = os.environ.get("TYPESAFE_API_KEY", "")
JEV_MODEL = os.environ.get("JEV_MODEL", "jev-latest")
TYPESAFE_URL = os.environ.get("TYPESAFE_URL", "https://api.typesafe.ai/v1/systemone")

# Below this confidence, Jev's shelf guess is flagged for review instead of trusted blindly.
SHELF_CONFIDENCE_FLOOR = float(os.environ.get("BRAIN_VAULT_SHELF_FLOOR", "0.45"))
TAG_THRESHOLD = float(os.environ.get("BRAIN_VAULT_TAG_THRESHOLD", "0.6"))
MAX_TAGS = 4
