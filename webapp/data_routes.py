"""
Data editor backend — add / change / delete entries of Data/word_list.py and
Data/verb_list.py from the web app, writing the real files in their real structure.
A self-contained Blueprint like search_routes.py / review_routes.py; webapp/app.py
only gains the two lines that register it. No existing route or mode is touched.

How the files are edited
------------------------
The two files are NOT regenerated. They contain comments, entries that span several
lines, hand-made blank-line groups and mixed indentation, and all of that has to
survive. So every operation is a surgical text edit at the exact position the Python
parser reports for the entry:

  update   only the key and/or value text of that one entry is replaced
  delete   the entry's line(s) are removed (its comma and trailing comment with it)
  add      one new line / block is appended at the end of the chapter / verb list

Everything else in the file stays byte-for-byte as it was, so `git diff` shows exactly
the entry you touched. Each edit is checked before it is written: the new file must
parse, and its contents must equal the old contents plus exactly the requested change
(all other chapters / verbs untouched, same order). Only then is the old file saved to
Data/backups/ (*.bak, newest 30 kept) and the new one swapped in atomically.

The editor reads the files from disk on every request, so it always shows the truth,
even right after a save. The rest of the app (quiz, search, ...) imported the data at
start-up; in debug mode Flask restarts itself when a .py file changes, which is how
they pick the change up (dev_reload.js refreshes the open screen afterwards).

Entries are addressed by their position ("no", 1-based, same numbering the review
screens show). Every write also sends what the user saw at that position
(expected_*); if the file changed in the meantime the write is refused instead of
hitting the wrong entry.
"""
import ast
import glob
import json
import os
import re
import tempfile
import threading
import time

from flask import Blueprint, current_app, jsonify, request

from Data import word_list as _word_list_module   # only used to map chapter number -> variable name
from webapp.chapters_data import CHAPTERS_ALL

data_bp = Blueprint("data_editor", __name__, url_prefix="/api/data")

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORD_FILE = os.path.join(_REPO_ROOT, "Data", "word_list.py")
VERB_FILE = os.path.join(_REPO_ROOT, "Data", "verb_list.py")
BACKUP_DIR = os.path.join(_REPO_ROOT, "Data", "backups")
BACKUPS_KEPT = 30

_LOCK = threading.Lock()

MAX_TERM_LEN = 120
MAX_VARIANTS = 12

# chapter number -> variable name in Data/word_list.py (found by identity, so it follows chapters_data.py)
_CHAPTER_VAR = {
    n: name
    for n, obj in CHAPTERS_ALL.items()
    for name, o in vars(_word_list_module).items()
    if o is obj and not name.startswith("_")
}

# verb fields: API key -> key in verb_list.py
_VERB_FIELDS = {
    "verb": "verb", "meaning": "meaning",
    "praesens": "präsens", "praeteritum": "präteritum", "perfekt": "perfekt",
}


class _ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


# ------------------------------------------------------------------ file helpers ----

def _read(path):
    with open(path, "rb") as f:
        return f.read().decode("utf-8")


def _backup(path):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stem = os.path.basename(path)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(BACKUP_DIR, f"{stem}.{stamp}.bak")
    n = 1
    while os.path.exists(dest):          # two saves within one second
        n += 1
        dest = os.path.join(BACKUP_DIR, f"{stem}.{stamp}_{n}.bak")
    with open(path, "rb") as src, open(dest, "wb") as out:
        out.write(src.read())
    old = sorted(glob.glob(os.path.join(BACKUP_DIR, f"{stem}.*.bak")))
    for p in old[:-BACKUPS_KEPT]:
        try:
            os.remove(p)
        except OSError:
            pass


def _write_atomic(path, text):
    folder = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".edit_", suffix=".tmp")   # not *.py: the reloader ignores it
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(text.encode("utf-8"))
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def _commit(path, new_text):
    _backup(path)
    _write_atomic(path, new_text)


# ------------------------------------------------------------- text-edit helpers ----

class _Source:
    """Maps ast positions (1-based line, UTF-8 byte column) to character offsets of the text."""

    def __init__(self, text):
        self.text = text
        self.nl = "\r\n" if "\r\n" in text else "\n"
        self.lines = text.split("\n")
        self.starts = [0]
        for line in self.lines[:-1]:
            self.starts.append(self.starts[-1] + len(line) + 1)

    def off(self, lineno, col):
        line = self.lines[lineno - 1]
        return self.starts[lineno - 1] + len(line.encode("utf-8")[:col].decode("utf-8"))

    def start(self, node):
        return self.off(node.lineno, node.col_offset)

    def end(self, node):
        return self.off(node.end_lineno, node.end_col_offset)

    def line_start(self, lineno):
        return self.starts[lineno - 1]

    def indent_of(self, lineno):
        line = self.lines[lineno - 1]
        return line[: len(line) - len(line.lstrip(" \t"))]

    def line_end(self, pos):
        i = self.text.find("\n", pos)
        return len(self.text) if i == -1 else i


_REST_OF_LINE = re.compile(r"[ \t\r]*,?[ \t\r]*(#[^\n]*)?")


def _apply(text, edits):
    """edits: (start, end, replacement) character spans, non-overlapping."""
    for s, e, r in sorted(edits, key=lambda x: x[0], reverse=True):
        text = text[:s] + r + text[e:]
    return text


def _lit(s):
    return json.dumps(s, ensure_ascii=False)


def _fmt_key(terms):
    return "(" + ", ".join(_lit(t) for t in terms) + ("," if len(terms) == 1 else "") + ")"


def _fmt_list(items):
    return "[" + ", ".join(_lit(t) for t in items) + "]"


def _remove_element(src, first, last, prev_last=None):
    """Edits that delete one element (dict entry / list item) spanning node `first`..`last`,
    including its trailing comma and comment when it owns its line(s)."""
    s, e = src.start(first), src.end(last)
    ls = src.line_start(first.lineno)
    before = src.text[ls:s]
    rest_end = src.line_end(e)
    rest = src.text[e:rest_end]
    if before.strip() == "" and _REST_OF_LINE.fullmatch(rest):
        return [(ls, min(rest_end + 1, len(src.text)), "")]          # whole lines
    m = re.match(r"[ \t]*,?[ \t]*", src.text[e:])
    return [(s, e + m.end(), "")]                                    # shares its line with other code


# ------------------------------------------------------------------- validation ----

def _clean_terms(values, label):
    if not isinstance(values, list):
        raise _ApiError(f"{label}: ungültige Eingabe.")
    out = []
    for v in values:
        if not isinstance(v, str):
            raise _ApiError(f"{label}: ungültige Eingabe.")
        v = " ".join(v.split())
        if not v:
            continue
        if len(v) > MAX_TERM_LEN:
            raise _ApiError(f"{label}: „{v[:30]}…“ ist zu lang (max. {MAX_TERM_LEN} Zeichen).")
        if v not in out:
            out.append(v)
    if not out:
        raise _ApiError(f"{label}: mindestens ein Eintrag nötig.")
    if len(out) > MAX_VARIANTS:
        raise _ApiError(f"{label}: höchstens {MAX_VARIANTS} Varianten.")
    return out


def _clean_verb(data):
    if not isinstance(data, dict):
        raise _ApiError("Ungültige Eingabe.")
    labels = {"verb": "Verb", "meaning": "Bedeutung", "praesens": "Präsens",
              "praeteritum": "Präteritum", "perfekt": "Perfekt"}
    out = {}
    for key, label in labels.items():
        v = data.get(key)
        if not isinstance(v, str):
            raise _ApiError(f"{label}: ungültige Eingabe.")
        v = " ".join(v.split())
        if not v:
            raise _ApiError(f"{label}: darf nicht leer sein.")
        if len(v) > MAX_TERM_LEN:
            raise _ApiError(f"{label}: zu lang (max. {MAX_TERM_LEN} Zeichen).")
        out[key] = v
    return out


def _get_no(body, total):
    no = body.get("no")
    if not isinstance(no, int) or isinstance(no, bool) or not (1 <= no <= total):
        raise _ApiError("Dieser Eintrag existiert nicht mehr — Liste neu laden.", 409)
    return no


# ------------------------------------------------------------------------- words ----

def _chapter_var(chapter):
    if not isinstance(chapter, int) or isinstance(chapter, bool) or chapter not in _CHAPTER_VAR:
        raise _ApiError("Bitte ein Kapitel von 1 bis 12 wählen.")
    return _CHAPTER_VAR[chapter]


def _parse_chapters(text):
    """-> (tree, {var: ast.Assign node}, {var: [(english tuple, german list), ...]})"""
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        raise _ApiError(f"Data/word_list.py hat einen Syntaxfehler (Zeile {e.lineno}) — bitte zuerst dort beheben.", 500)
    nodes, data = {}, {}
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Dict)):
            name = node.targets[0].id
            if any(k is None for k in node.value.keys):
                continue
            try:
                entries = [(tuple(ast.literal_eval(k)), list(ast.literal_eval(v)))
                           for k, v in zip(node.value.keys, node.value.values)]
            except (ValueError, SyntaxError, TypeError):
                continue
            if len(set(k for k, _ in entries)) != len(entries):
                raise _ApiError(f"{name} enthält doppelte englische Einträge — bitte zuerst manuell bereinigen.", 500)
            nodes[name], data[name] = node, entries
    return tree, nodes, data


def _words_payload(chapter, entries):
    return {
        "chapter": chapter, "total": len(entries),
        "entries": [{"no": i, "english": list(k), "german": list(v)} for i, (k, v) in enumerate(entries, start=1)],
        "auto_reload": bool(current_app.debug),
    }


def _edit_words(chapter, op, body):
    """Returns the chapter's entries after the operation (already written to disk)."""
    var = _chapter_var(chapter)
    text = _read(WORD_FILE)
    _, nodes, before = _parse_chapters(text)
    if var not in nodes:
        raise _ApiError(f"{var} nicht in Data/word_list.py gefunden.", 500)
    node, entries = nodes[var], before[var]
    src = _Source(text)
    d = node.value
    expected = list(entries)
    edits = []

    if op in ("update", "delete"):
        no = _get_no(body, len(entries))
        i = no - 1
        seen = body.get("expected_english")
        if not isinstance(seen, list) or tuple(seen) != entries[i][0]:
            raise _ApiError("Die Liste hat sich inzwischen geändert — bitte neu laden.", 409)

    if op in ("add", "update"):
        english = _clean_terms(body.get("english"), "Englisch")
        german = _clean_terms(body.get("german"), "Deutsch")
        key = tuple(english)
        for j, (k, _) in enumerate(entries):
            if k == key and not (op == "update" and j == i):
                raise _ApiError(f"Diesen englischen Eintrag gibt es schon in Kapitel {chapter} (Nr. {j + 1}).", 409)

    if op == "update":
        kn, vn = d.keys[i], d.values[i]
        if key != entries[i][0]:
            edits.append((src.start(kn), src.end(kn), _fmt_key(key)))
        if german != entries[i][1]:
            edits.append((src.start(vn), src.end(vn), _fmt_list(german)))
        expected[i] = (key, german)
    elif op == "delete":
        edits += _remove_element(src, d.keys[i], d.values[i])
        del expected[i]
    elif op == "add":
        new_entry = f"{_fmt_key(key)}: {_fmt_list(german)},"
        close = src.end(d) - 1                                     # the closing brace
        if entries:
            last_v = d.values[-1]
            le = src.end(last_v)
            indent = src.indent_of(d.keys[-1].lineno)
            between = src.text[le:close]
            has_comma = re.match(r"[ \t]*,", between) is not None
            close_ls = src.line_start(d.end_lineno)
            if src.text[close_ls:close].strip() == "":              # brace alone on its line (the normal case)
                if not has_comma:
                    edits.append((le, le, ","))
                edits.append((close_ls, close_ls, indent + new_entry + src.nl))
            else:
                ins = le + (re.match(r"[ \t]*,", between).end() if has_comma else 0)
                edits.append((ins, ins, ("" if has_comma else ",") + src.nl + indent + new_entry))
        else:
            edits.append((close, close, src.nl + "    " + new_entry + src.nl))
        expected.append((key, german))
    else:
        raise _ApiError("Unbekannte Aktion.")

    new_text = _apply(text, edits) if edits else text
    if new_text != text:
        # the new file must parse and contain exactly: all old data, with only this chapter changed as requested
        _, _, after = _parse_chapters(new_text)
        want = dict(before)
        want[var] = expected
        if after != want:
            raise _ApiError("Interner Fehler: die Änderung wurde nicht geschrieben, weil das Ergebnis nicht dem Wunsch entsprach.", 500)
        _commit(WORD_FILE, new_text)
    return expected


# ------------------------------------------------------------------------ verbs ----

def _parse_verbs(text):
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        raise _ApiError(f"Data/verb_list.py hat einen Syntaxfehler (Zeile {e.lineno}) — bitte zuerst dort beheben.", 500)
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "verbs" and isinstance(node.value, ast.List)):
            try:
                return node, [ast.literal_eval(e) for e in node.value.elts]
            except (ValueError, SyntaxError):
                break
    raise _ApiError("`verbs = [ ... ]` nicht in Data/verb_list.py gefunden.", 500)


def _verbs_payload(verbs):
    return {
        "total": len(verbs),
        "entries": [{"no": i, "verb": v["verb"], "meaning": v["meaning"], "praesens": v["präsens"],
                     "praeteritum": v["präteritum"], "perfekt": v["perfekt"]}
                    for i, v in enumerate(verbs, start=1)],
        "auto_reload": bool(current_app.debug),
    }


def _edit_verbs(op, body):
    text = _read(VERB_FILE)
    node, verbs = _parse_verbs(text)
    src = _Source(text)
    elts = node.value.elts
    expected = [dict(v) for v in verbs]
    edits = []

    if op in ("update", "delete"):
        no = _get_no(body, len(verbs))
        i = no - 1
        if body.get("expected_verb") != verbs[i]["verb"]:
            raise _ApiError("Die Liste hat sich inzwischen geändert — bitte neu laden.", 409)

    if op in ("add", "update"):
        clean = _clean_verb(body)
        mapped = {_VERB_FIELDS[k]: v for k, v in clean.items()}
        for j, v in enumerate(verbs):
            if v["verb"].casefold() == mapped["verb"].casefold() and not (op == "update" and j == i):
                raise _ApiError(f"„{mapped['verb']}“ gibt es schon in der Verbliste (Nr. {j + 1}).", 409)

    if op == "update":
        el = elts[i]
        for k, v in zip(el.keys, el.values):
            new = mapped[k.value]
            if new != v.value:
                edits.append((src.start(v), src.end(v), _lit(new)))
        expected[i] = {**verbs[i], **mapped}
    elif op == "delete":
        el = elts[i]
        edits += _remove_element(src, el, el)
        if i == len(elts) - 1 and i > 0:            # last item: the previous item's comma has to go too
            pe = src.end(elts[i - 1])
            m = re.match(r"[ \t]*,", src.text[pe:])
            if m:
                edits.append((pe, pe + m.end(), ""))
        del expected[i]
    elif op == "add":
        if not elts:
            raise _ApiError("Die Verbliste ist leer — das erste Verb bitte direkt in Data/verb_list.py anlegen.", 500)
        last = elts[-1]
        brace_indent = src.indent_of(last.lineno)
        field_indent = src.indent_of(last.keys[0].lineno)
        fields = []
        for k in last.keys:                          # same key order as the existing entries
            fields.append(f"{field_indent}{_lit(k.value)}: {_lit(mapped[k.value])}")
        block = brace_indent + "{" + src.nl + ("," + src.nl).join(fields) + src.nl + brace_indent + "}"
        le = src.end(last)
        m = re.match(r"[ \t]*,", src.text[le:])
        if m:
            edits.append((le + m.end(), le + m.end(), src.nl + block + ","))
        else:
            edits.append((le, le, "," + src.nl + block))
        expected.append(mapped)
    else:
        raise _ApiError("Unbekannte Aktion.")

    new_text = _apply(text, edits) if edits else text
    if new_text != text:
        _, after = _parse_verbs(new_text)
        if after != expected:
            raise _ApiError("Interner Fehler: die Änderung wurde nicht geschrieben, weil das Ergebnis nicht dem Wunsch entsprach.", 500)
        _commit(VERB_FILE, new_text)
    return expected


# ------------------------------------------------------------------------ routes ----

def _guard(fn):
    with _LOCK:
        try:
            return jsonify(fn())
        except _ApiError as e:
            return jsonify({"error": e.message}), e.status
        except OSError as e:
            return jsonify({"error": f"Datei konnte nicht gelesen/geschrieben werden: {e}"}), 500


def _body():
    return request.get_json(force=True, silent=True) or {}


@data_bp.get("/words/<int:chapter>")
def words_list(chapter):
    def run():
        var = _chapter_var(chapter)
        _, _, data = _parse_chapters(_read(WORD_FILE))
        if var not in data:
            raise _ApiError(f"{var} nicht in Data/word_list.py gefunden.", 500)
        return _words_payload(chapter, data[var])
    return _guard(run)


@data_bp.post("/words/<op>")
def words_edit(op):
    body = _body()
    if op not in ("add", "update", "delete"):
        return jsonify({"error": "Unbekannte Aktion."}), 404

    def run():
        chapter = body.get("chapter")
        entries = _edit_words(chapter, op, body)
        out = _words_payload(chapter, entries)
        out["changed_no"] = len(entries) if op == "add" else body.get("no")
        return out
    return _guard(run)


@data_bp.get("/verbs")
def verbs_list():
    def run():
        _, verbs = _parse_verbs(_read(VERB_FILE))
        return _verbs_payload(verbs)
    return _guard(run)


@data_bp.post("/verbs/<op>")
def verbs_edit(op):
    body = _body()
    if op not in ("add", "update", "delete"):
        return jsonify({"error": "Unbekannte Aktion."}), 404

    def run():
        verbs = _edit_verbs(op, body)
        out = _verbs_payload(verbs)
        out["changed_no"] = len(verbs) if op == "add" else body.get("no")
        return out
    return _guard(run)