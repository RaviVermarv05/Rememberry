"""
Mode 7 (verbs) for the web app: a self-contained Blueprint, same pattern as
search_routes.py / review_routes.py / context_routes.py. Nothing existing is modified.

Mirrors handle_verb_mode() in modes_and_logics/logics.py and practice_verbs() in
modes_and_logics/verb.py:

  review    -> same entries review() prints for verb records
               (verb -> meaning, then präsens | präteritum | perfekt)
  practice  -> every verb appears exactly once, in random order. One random value
               (meaning / verb / präsens / präteritum / perfekt) is shown as the
               clue; the other four are asked in random order, ONE attempt each.
               Answers are compared with strip().lower(), exactly like verb.py's
               normalize_answer(). Typing 'q' quits (no summary, like the CLI).
               The final score is correct / (verbs * 4), mistakes are listed.

The real apply_range_filter(), check_range(), Data.verb_list.verbs and
messages.Quiz_ger_eng are used as they are. The only thing copied is the field
list + labels, because verb.py keeps them inside practice_verbs() and they can't
be imported without editing that file.

Routes live under /api/verbmode so they don't clash with the existing
GET /api/verbs in app.py.
"""
import random
import uuid

from flask import Blueprint, jsonify, request

from Data.verb_list import verbs
from messages import Quiz_ger_eng
from modes_and_logics.logics import apply_range_filter
from webapp.range_check import check_range

verbs_bp = Blueprint("verbmode", __name__, url_prefix="/api/verbmode")

# Same fields and labels as verb.py (practice_verbs -> FIELDS / get_label)
FIELDS = ["meaning", "verb", "präsens", "präteritum", "perfekt"]
LABELS = {
    "meaning": "Meaning",
    "verb": "Verb",
    "präsens": "Präsens (er/sie/es)",
    "präteritum": "Präteritum",
    "perfekt": "Perfekt",
}

SESSIONS = {}


def _normalize(answer):
    return answer.strip().lower()  # verb.py: normalize_answer()


def _ranged(body):
    """(verbs_in_range, total, start, end, error_response) — real helpers, untouched."""
    total = len(verbs)
    start, end, err = check_range(total, body.get("start"), body.get("end"))
    if err:
        return None, total, None, None, err
    return apply_range_filter(verbs, start, end), total, start, end, None


@verbs_bp.post("/review")
def review():
    body = request.get_json(force=True, silent=True) or {}
    chosen, total, start, end, err = _ranged(body)
    if err:
        return err
    entries = [
        {
            "no": i, "verb": v["verb"], "meaning": v["meaning"],
            "präsens": v["präsens"], "präteritum": v["präteritum"], "perfekt": v["perfekt"],
        }
        for i, v in enumerate(chosen, start=1)
    ]
    return jsonify({
        "total": total, "range": {"start": start, "end": end} if start is not None else None,
        "entries": entries,
    })


@verbs_bp.post("/start")
def start():
    body = request.get_json(force=True, silent=True) or {}
    chosen, _total, _start, _end, err = _ranged(body)
    if err:
        return err
    pool = list(chosen)  # copy, like verbs.copy() in verb.py
    if not pool:
        return jsonify({"error": "Keine Verben ausgewählt."}), 400
    random.shuffle(pool)
    sid = str(uuid.uuid4())
    SESSIONS[sid] = {
        "verbs": pool, "vi": -1, "fi": 0, "cur": None,
        "correct": 0, "wrong": 0, "mistakes": [],
    }
    return jsonify({"session_id": sid, "total_verbs": len(pool)})


def _session():
    body = request.get_json(force=True, silent=True) or {}
    return SESSIONS.get(body.get("session_id")), body


def _question(s):
    cur = s["cur"]
    field = cur["answer_fields"][s["fi"]]
    verb_data = s["verbs"][s["vi"]]
    return {
        "done": False,
        "verb_number": s["vi"] + 1,
        "total_verbs": len(s["verbs"]),
        "clue": {"label": LABELS[cur["clue_field"]], "value": verb_data[cur["clue_field"]]},
        "question": {"label": LABELS[field], "number": s["fi"] + 1, "of": len(cur["answer_fields"])},
        "progress": {"completed": s["vi"], "total": len(s["verbs"])},
    }


def _results(s):
    total_questions = len(s["verbs"]) * 4  # verb.py: each verb produces exactly 4 questions
    accuracy = (s["correct"] / total_questions) * 100
    return {
        "done": True, "correct": s["correct"], "wrong": s["wrong"],
        "accuracy": round(accuracy, 1), "mistakes": s["mistakes"],
        "perfect": not s["mistakes"],
    }


@verbs_bp.post("/next")
def next_question():
    s, _ = _session()
    if s is None:
        return jsonify({"error": "unknown session"}), 404
    cur = s["cur"]
    if cur and not cur["answered"]:
        return jsonify(_question(s))  # resend the open question (e.g. page re-render)
    if cur and s["fi"] + 1 < len(cur["answer_fields"]):
        s["fi"] += 1                  # next of the 4 fields for the same verb
        cur["answered"] = False
        return jsonify(_question(s))
    s["vi"] += 1                      # next verb
    if s["vi"] >= len(s["verbs"]):
        return jsonify(_results(s))
    clue_field = random.choice(FIELDS)
    answer_fields = [f for f in FIELDS if f != clue_field]
    random.shuffle(answer_fields)
    s["fi"] = 0
    s["cur"] = {"clue_field": clue_field, "answer_fields": answer_fields, "answered": False}
    return jsonify(_question(s))


@verbs_bp.post("/answer")
def answer():
    s, body = _session()
    if s is None or s["cur"] is None:
        return jsonify({"error": "no active round"}), 404
    cur = s["cur"]
    if cur["answered"]:
        return jsonify({"result": "duplicate"})
    raw = body.get("answer") or ""
    if raw.strip().lower() == "q":    # verb.py: 'q' quits
        SESSIONS.pop(body.get("session_id"), None)
        return jsonify({"result": "quit"})

    field = cur["answer_fields"][s["fi"]]
    verb_data = s["verbs"][s["vi"]]
    user_answer = _normalize(raw)
    correct_answer = _normalize(str(verb_data[field]))
    cur["answered"] = True
    last_field = s["fi"] + 1 >= len(cur["answer_fields"])

    if user_answer == correct_answer:
        s["correct"] += 1
        return jsonify({"result": "correct", "message": Quiz_ger_eng.right_ans, "verb_complete": last_field})

    s["wrong"] += 1
    s["mistakes"].append({
        "verb": verb_data["verb"],
        "clue": verb_data[cur["clue_field"]],
        "question": LABELS[field],
        "your_answer": user_answer,
        "correct_answer": verb_data[field],
    })
    return jsonify({
        "result": "wrong", "message": Quiz_ger_eng.wrong_ans,
        "correct_answer": verb_data[field], "verb_complete": last_field,
    })


@verbs_bp.post("/quit")
def quit_session():
    _, body = _session()
    SESSIONS.pop(body.get("session_id"), None)
    return jsonify({"result": "quit"})