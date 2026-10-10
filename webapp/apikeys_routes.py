"""
API keys in the dashboard Settings page: a self-contained Blueprint, same pattern as
search_routes.py / context_routes.py / verbs_routes.py. Nothing existing is modified.

What it does
  GET  /api/settings/keys  -> which keys are set (never the key itself, only the last 4 chars)
  POST /api/settings/keys  -> {"name": "GROQ_API_KEY", "value": "..."}
                              1. puts the key into os.environ, so it works immediately
                                 (context_routes.py / search_routes.py read os.getenv()
                                 on every request - no restart needed)
                              2. writes it to <project root>/.env, so it survives a restart
                                 and is also picked up by the terminal version

Only the two keys the project uses can be set (KEYS below). The .env file is already in
.gitignore. The key is never logged and never sent back to the browser.
"""
import os
import re
import tempfile
from urllib.parse import urlparse

from flask import Blueprint, jsonify, request

apikeys_bp = Blueprint("apikeys", __name__, url_prefix="/api/settings/keys")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(REPO_ROOT, ".env")  # module-level so tests can point it elsewhere

# name -> what the Settings page shows
KEYS = {
    "GROQ_API_KEY": {
        "label": "Groq",
        "used_for": "Kontext-Modus (KI-Hinweise)",
        "help_url": "https://console.groq.com/keys",
        "placeholder": "gsk_…",
    },
    "PONS_API_KEY": {
        "label": "PONS",
        "used_for": "Online-Suche (Wörterbuch)",
        "help_url": "https://en.pons.com/open_dict/public_api/secret",
        "placeholder": "PONS-Secret",
    },
}

# No whitespace/control chars, and none of the characters that would break a .env line
# (quotes, backslash, '#', '$' - python-dotenv treats them specially).
_VALID_VALUE = re.compile(r"^[^\s\"'`\\#$\x00-\x1f\x7f]{8,512}$")


def _is_placeholder(value):
    """The template in requirements.txt uses e.g. your_groq_api_key_here."""
    v = value.strip().lower()
    return v.startswith("your_") and v.endswith("_here")


def _current(name):
    value = (os.environ.get(name) or "").strip()
    return "" if (not value or _is_placeholder(value)) else value


def _mask(value):
    return ("••••" + value[-4:]) if len(value) >= 12 else "••••"


def _status():
    out = []
    for name, meta in KEYS.items():
        value = _current(name)
        out.append({
            "name": name,
            "label": meta["label"],
            "used_for": meta["used_for"],
            "help_url": meta["help_url"],
            "placeholder": meta["placeholder"],
            "set": bool(value),
            "masked": _mask(value) if value else "",
        })
    return out


@apikeys_bp.before_request
def _same_origin_only():
    """The app has CORS(app) wide open. Without this, any website open in the same browser
    could read/overwrite the keys through http://127.0.0.1:5000. Browsers always send
    Origin on cross-site requests, so a mismatch is refused."""
    origin = request.headers.get("Origin")
    if origin and urlparse(origin).netloc != request.host:
        return jsonify({"error": "Anfrage von fremder Herkunft abgelehnt."}), 403


def _write_env(name, value):
    """Set/replace NAME=value in .env, keeping every other line (comments, other keys,
    order) exactly as it was. Atomic: temp file + os.replace."""
    try:
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        existing = True
    except FileNotFoundError:
        lines, existing = [], False

    pattern = re.compile(r"^\s*(?:export\s+)?" + re.escape(name) + r"\s*=")
    new_line = f"{name}={value}"
    replaced = False
    out = []
    for line in lines:
        if pattern.match(line):
            if not replaced:
                out.append(new_line)  # first occurrence replaced, duplicates dropped
                replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(new_line)

    directory = os.path.dirname(ENV_PATH) or "."
    fd, tmp = tempfile.mkstemp(prefix=".env.", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(out) + "\n")
        if existing:
            try:
                os.chmod(tmp, os.stat(ENV_PATH).st_mode & 0o777)
            except OSError:
                pass
        else:
            try:
                os.chmod(tmp, 0o600)  # new file holding a secret: owner only
            except OSError:
                pass
        os.replace(tmp, ENV_PATH)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


@apikeys_bp.get("")
def get_keys():
    return jsonify({"keys": _status()})


@apikeys_bp.post("")
def set_key():
    body = request.get_json(force=True, silent=True) or {}
    name = body.get("name")
    value = body.get("value")

    if name not in KEYS:
        return jsonify({"error": "Unbekannter Schlüssel."}), 400
    if not isinstance(value, str) or not value.strip():
        return jsonify({"error": "Bitte einen Schlüssel eingeben."}), 400
    value = value.strip()
    if not _VALID_VALUE.match(value):
        return jsonify({
            "error": "Das sieht nicht wie ein gültiger Schlüssel aus "
                     "(mind. 8 Zeichen, keine Leerzeichen oder Anführungszeichen)."
        }), 400
    if _is_placeholder(value):
        return jsonify({"error": "Das ist nur der Platzhalter aus der Vorlage, nicht dein echter Schlüssel."}), 400

    os.environ[name] = value  # effective right away for this run
    persisted = True
    try:
        _write_env(name, value)
    except OSError:
        persisted = False  # still works until the server restarts

    return jsonify({"keys": _status(), "persisted": persisted, "saved": name})