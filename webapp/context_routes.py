"""
Mode 6 (context mode) for the web app: a self-contained Blueprint, same pattern
as search_routes.py / review_routes.py. Nothing existing is modified.

Mirrors run_context_mode() in modes_and_logics/description_ai.py: the words are
shuffled with logics.schuflle(), every German word gets an AI clue from the real
get_hint(), and the player types the German word. Differences, on purpose:
  - the CLI's `ger_word[4:]` shortcut is replaced by logics.split_article(), so a
    word without an article can't be "solved" by typing its last letters
  - attempts per word follow Settings.trials, like modes 1 and 2
  - the next clue is generated in the background while you answer the current one
  - a clue that leaks the target word is masked with ___
"""
import os
import re
import uuid
from concurrent.futures import ThreadPoolExecutor

from flask import Blueprint, jsonify, request

from messages import Quiz_eng_ger
from modes_and_logics import description_ai
from modes_and_logics.logics import apply_range_filter, schuflle, split_article
from modes_and_logics.main_settings import Settings
from webapp.chapters_data import CHAPTERS_ALL  # shared with search/review/audio routes
from webapp.range_check import check_range

context_bp = Blueprint("context", __name__, url_prefix="/api/context")

SESSIONS = {}
POOL = ThreadPoolExecutor(max_workers=2)
AI_FAILED = "No AI description available"  # what get_hint() returns when Groq fails


def make_hint(ger):
    """Real get_hint(); None if it failed. Masks the target word if the model leaked it."""
    text = (description_ai.get_hint(ger) or "").strip()
    if not text or text.startswith(AI_FAILED):
        return None
    _, bare = split_article(ger)
    pattern = r"\b" + re.escape(bare) + (r"\w{0,3}" if len(bare) >= 5 else "") + r"\b"
    return re.sub(pattern, "___", text, flags=re.I)


def hint_future(s, i):
    if i not in s["hints"]:
        s["hints"][i] = POOL.submit(make_hint, s["words"][i][0])
    return s["hints"][i]


def get_session():
    body = request.get_json(force=True, silent=True) or {}
    return SESSIONS.get(body.get("session_id")), body


def reveal(s):
    ger, eng = s["words"][s["idx"]]
    return {"word": ger, "english": eng}


def results(s):
    total = s["correct"] + len(s["missed"])
    return {
        "done": True, "correct": s["correct"], "total": total, "first_try": s["first_try"],
        "rate": round(s["correct"] / total * 100, 2) if total else 0,
        "skipped": s["skipped"], "missed": s["missed"],
    }


@context_bp.post("/start")
def start():
    if not os.getenv("GROQ_API_KEY"):
        return jsonify({"error": "GROQ_API_KEY fehlt. Lege eine .env-Datei im Projektordner an."}), 400
    body = request.get_json(force=True, silent=True) or {}
    raw = {}
    for n in body.get("chapters") or list(CHAPTERS_ALL):
        raw.update(CHAPTERS_ALL.get(n, {}))
    start_, end_, err = check_range(len(raw), body.get("start"), body.get("end"))
    if err:
        return err
    raw = schuflle(apply_range_filter(raw, start_, end_))  # real functions, untouched
    words = [(ger, " / ".join(eng)) for eng, ger_list in raw.items() for ger in ger_list]
    if not words:
        return jsonify({"error": "Keine Wörter ausgewählt."}), 400
    sid = str(uuid.uuid4())
    SESSIONS[sid] = {"words": words, "idx": -1, "cur": None, "hints": {}, "correct": 0,
                     "first_try": 0, "missed": [], "skipped": 0}
    hint_future(SESSIONS[sid], 0)  # start the first clue right away
    return jsonify({"session_id": sid, "total_words": len(words)})


@context_bp.post("/next")
def next_word():
    s, body = get_session()
    if s is None:
        return jsonify({"error": "unknown session"}), 404
    cur = s["cur"]
    if body.get("retry") and cur:            # "Anderer Hinweis": new clue, same word
        s["hints"].pop(s["idx"], None)
    elif not cur or cur["done"]:             # otherwise advance (or resend the open word)
        s["idx"] += 1
        if s["idx"] >= len(s["words"]):
            return jsonify(results(s))
        s["cur"] = cur = {"wrong": 0, "done": False}
    i = s["idx"]
    try:
        hint = hint_future(s, i).result(timeout=45)
    except Exception:
        hint = None
    if hint is None:
        s["hints"].pop(i, None)              # so "Erneut versuchen" asks Groq again
    elif i + 1 < len(s["words"]):
        hint_future(s, i + 1)                # prefetch the next clue
    return jsonify({"done": False, "hint": hint, "hint_ok": hint is not None, "wrong": cur["wrong"],
                    "trials": Settings.trials, "progress": {"completed": i, "total": len(s["words"])}})


@context_bp.post("/answer")
def answer():
    s, body = get_session()
    if s is None or s["cur"] is None:
        return jsonify({"error": "no active round"}), 404
    cur = s["cur"]
    if cur["done"]:
        return jsonify({"result": "duplicate", "round_complete": True})
    ger, eng = s["words"][s["idx"]]
    _, bare = split_article(ger)
    a = (body.get("answer") or "").lower().strip()
    if a and a in (ger.lower().strip(), bare):
        cur["done"] = True
        s["correct"] += 1
        s["first_try"] += cur["wrong"] == 0
        return jsonify({"result": "correct", "message": Quiz_eng_ger.right_ans, **reveal(s)})
    cur["wrong"] += 1
    if cur["wrong"] >= Settings.trials:
        cur["done"] = True
        s["missed"].append({"de": ger, "en": eng})
        return jsonify({"result": "revealed", "message": Quiz_eng_ger.wrong_ans, **reveal(s)})
    return jsonify({"result": "wrong", "message": Quiz_eng_ger.wrong_ans,
                    "wrong": cur["wrong"], "trials": Settings.trials})


@context_bp.post("/finish")
def finish():
    """kind='giveup' counts as missed and reveals; kind='skip' (clue failed) isn't counted."""
    s, body = get_session()
    if s is None or s["cur"] is None or s["cur"]["done"]:
        return jsonify({"error": "no active round"}), 404
    s["cur"]["done"] = True
    if body.get("kind") == "skip":
        s["skipped"] += 1
        return jsonify({"result": "skipped"})
    ger, eng = s["words"][s["idx"]]
    s["missed"].append({"de": ger, "en": eng})
    return jsonify({"result": "revealed", "message": Quiz_eng_ger.wrong_ans, **reveal(s)})