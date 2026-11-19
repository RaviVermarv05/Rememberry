"""
Chapter aliases — give any chapter your own display name ("Kapitel 3" -> "Reisen & Verkehr").

A self-contained Blueprint like search_routes.py / review_routes.py: webapp/app.py only gains the
two lines that register it. Nothing that already exists is read differently or changed:

  * Data/word_list.py, Data/chapters.py and every existing route are never touched.
  * /api/chapters still returns the default names ("Kapitel N", "B2.1 · Kapitel N") exactly as before;
    the browser (static/chapter_alias.js) lays the alias on top when it draws a chapter's name.
  * An alias is purely a display name. Chapter ids, quiz / review / audio / search endpoints and the
    data editor keep using the internal id, so no mode can break because of a name.

Storage: Data/chapter_aliases.json (created on the first save, ignored by git like settings.json)

    {"3": {"alias": "Reisen & Verkehr", "var": "chapter_three"}}

The chapter's variable name is stored next to the id. If a chapter is deleted and a later chapter
happens to get the same id, the old alias is NOT shown on it (the variable differs), so a name can
never end up on the wrong chapter.

Routes
  GET  /api/chapter-aliases              -> {"aliases": {"3": "Reisen & Verkehr"}, "max_length": 40}
  POST /api/chapter-aliases              body {"id": 3, "alias": "Reisen"}    -> saves
                                         body {"id": 3, "alias": ""}          -> back to the default name
"""
import ast
import json
import os
import re
import sys
import tempfile
import threading

from flask import Blueprint, jsonify, request

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from webapp.chapter_registry import chapter_vars_from_source, resolve

alias_bp = Blueprint("chapter_aliases", __name__)

WORD_FILE = os.path.join(_REPO_ROOT, "Data", "word_list.py")
REGISTRY_FILE = os.path.join(_REPO_ROOT, "Data", "chapters.py")
ALIAS_FILE = os.path.join(_REPO_ROOT, "Data", "chapter_aliases.json")

MAX_LENGTH = 40
_LOCK = threading.Lock()
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


# ------------------------------------------------------------------ live chapter list ----
# Read from the files every time (same sources the data editor uses), so a chapter that was just
# added or deleted in the editor is known here without restarting the server.

def _read_text(path):
    with open(path, "rb") as f:
        return f.read().decode("utf-8")


def _read_registry():
    if not os.path.exists(REGISTRY_FILE):
        return None
    try:
        tree = ast.parse(_read_text(REGISTRY_FILE))
        for node in tree.body:
            if (isinstance(node, ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name) and node.targets[0].id == "CHAPTERS"):
                return ast.literal_eval(node.value)
    except (SyntaxError, ValueError, OSError, UnicodeDecodeError):
        pass
    return None


def _live_vars():
    """{id: variable name} of the chapters that exist right now."""
    try:
        names = chapter_vars_from_source(_read_text(WORD_FILE))
    except (OSError, UnicodeDecodeError):
        return {}
    return {i["id"]: i["var"] for i in resolve(_read_registry(), names)}


# ---------------------------------------------------------------------------- storage ----

def _load():
    """The stored aliases as {"3": {"alias": ..., "var": ...}}; a missing / broken file means none."""
    try:
        with open(ALIAS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    clean = {}
    for k, v in data.items():
        if (isinstance(k, str) and k.isdigit() and isinstance(v, dict)
                and isinstance(v.get("alias"), str) and v["alias"].strip()
                and isinstance(v.get("var"), str)):
            clean[k] = {"alias": v["alias"], "var": v["var"]}
    return clean


def _save(data):
    """Atomic write: a crash half-way can never leave a broken aliases file behind."""
    folder = os.path.dirname(ALIAS_FILE)
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".alias_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp, ALIAS_FILE)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _clean_alias(value):
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError("Der Name muss Text sein.")
    text = " ".join(_CONTROL.sub(" ", value).split())      # no control characters, tidy spaces
    if len(text) > MAX_LENGTH:
        raise ValueError(f"Der Name ist zu lang (höchstens {MAX_LENGTH} Zeichen).")
    return text


def _visible(stored, live):
    """Only aliases whose chapter still exists with the same variable."""
    return {k: v["alias"] for k, v in stored.items() if live.get(int(k)) == v["var"]}


# ---------------------------------------------------------------------------- routes ----

@alias_bp.get("/api/chapter-aliases")
def aliases_get():
    return jsonify({"aliases": _visible(_load(), _live_vars()), "max_length": MAX_LENGTH})


@alias_bp.post("/api/chapter-aliases")
def aliases_set():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "Ungültige Anfrage."}), 400
    cid = body.get("id")
    if not isinstance(cid, int) or isinstance(cid, bool):
        return jsonify({"error": "Ungültige Kapitel-Nummer."}), 400
    try:
        alias = _clean_alias(body.get("alias"))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    live = _live_vars()
    if cid not in live:
        return jsonify({"error": "Dieses Kapitel gibt es nicht (mehr) — bitte neu laden."}), 409

    with _LOCK:
        stored = _load()
        # drop leftovers of deleted chapters while we are writing anyway
        stored = {k: v for k, v in stored.items() if live.get(int(k)) == v["var"]}
        if alias:
            stored[str(cid)] = {"alias": alias, "var": live[cid]}
        else:
            stored.pop(str(cid), None)
        try:
            _save(stored)
        except OSError as e:
            return jsonify({"error": f"Konnte nicht gespeichert werden: {e}"}), 500
    return jsonify({"aliases": _visible(stored, live), "id": cid, "alias": alias or None})