"""
Flask API for Rememberry — corrected + extended from the api.py draft.

Everything that decides right/wrong, tracks trials, picks the next word,
classifies an error, or produces user-facing text calls into the real,
unmodified project files:
    Data/word_list.py, Data/verb_list.py         (vocab data)
    messages.py                                   (all user-facing strings)
    modes_and_logics/main_settings.py             (Settings.trials / show_article / shuffle_mode)
    modes_and_logics/logics.py                    (pick_next_word, apply_range_filter)
    modes_and_logics/error_classifier.py          (ErrorAnalyzer.classify_error / closest_term)

app.py itself only does two things no existing file does in a reusable form:
  1. flattens a per-round interactive loop (built around input()/print()) into
     stateless request/response steps, using the exact same comparisons main.py
     makes inside quiz_eng_ger()
  2. serializes the results to JSON

No quiz rule (matching, trials, article-checking, scoring, error classification)
is duplicated or re-decided in JavaScript — the frontend only renders whatever
this API returns.
"""
import json
import os
import sys
import uuid

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# Make the project root (one level up from webapp/) importable, the same way
# main.py expects to be run from the repo root.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from Data.word_list import (
    chapter_one, chapter_two, chapter_eight, chapter_nine,
    chapter_ten, chapter_eleven, chapter_twelve,
)
from Data.verb_list import verbs
from messages import Quiz_eng_ger, Quiz_ger_eng, German_feedback, Eng_feedback, Range_message
from modes_and_logics.main_settings import Settings
from modes_and_logics.logics import (
    pick_next_word, apply_range_filter, split_article, accepted_english_set,
)
from modes_and_logics.error_classifier import ErrorAnalyzer
from webapp.search_routes import search_bp  # mode 3 (search) — self-contained blueprint, see that file

app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app)
app.register_blueprint(search_bp)  # adds /api/search and /api/search/online (mode 3), nothing else changed


@app.get("/")
def index():
    return app.send_static_file("index.html")

CHAPTERS = {
    1: chapter_one, 2: chapter_two, 8: chapter_eight, 9: chapter_nine,
    10: chapter_ten, 11: chapter_eleven, 12: chapter_twelve,
}

SESSIONS = {}  # session_id -> dict, in-memory (this is a single-user local tool, same as the CLI)
SESSIONS2 = {}  # session_id -> dict, for the Deutsch -> Englisch (mode 2) rounds


def merge_chapters(chapter_numbers):
    merged = {}
    for n in chapter_numbers:
        if n in CHAPTERS:
            merged.update(CHAPTERS[n])
    return merged


from webapp.range_check import check_range  # split out so review_routes.py (mode 4) can reuse it too


def build_vocab_pairs(raw_vocab):
    """Exactly mirrors main.py lines 255-266."""
    vocab_pairs = []
    for eng_terms, ger_list in raw_vocab.items():
        for ger in ger_list:
            vocab_pairs.append((eng_terms, ger))
    remaining = []
    for eng, _ in vocab_pairs:
        if eng not in remaining:
            remaining.append(eng)
    return vocab_pairs, remaining


# ---------------------------------------------------------------- vocab / verbs (browsing) ----

def vocabulary_to_json(vocabulary):
    """german_words is always list[str] in the real data — never a dict."""
    result = []
    for english_terms, german_words in vocabulary.items():
        result.append({
            "en": ", ".join(english_terms) if english_terms else "",
            "de": list(german_words),
        })
    return result


@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------- settings ----
# The dashboard's settings screen edits the same Settings class the quiz logic
# already reads (trials, show_article, shuffle_mode, sound_enable, volume_limit),
# so a change applies to the very next answer. Values are saved to
# webapp/settings.json and re-applied on the next start.

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")


def current_settings():
    return {
        "trials": Settings.trials,
        "show_article": Settings.show_article,
        "shuffle": Settings.shuffle_mode,
        "sound_enable": Settings.sound_enable,
        "volume": Settings.volume_limit,
    }


def parse_settings(body):
    """Validate the incoming values; only the keys that are present are returned."""
    clean = {}
    if "trials" in body:
        t = body["trials"]
        if isinstance(t, bool) or not isinstance(t, int) or not 1 <= t <= 5:
            raise ValueError("Versuche müssen eine ganze Zahl von 1 bis 5 sein.")
        clean["trials"] = t
    for key in ("show_article", "shuffle", "sound_enable"):
        if key in body:
            if not isinstance(body[key], bool):
                raise ValueError(f"'{key}' muss true oder false sein.")
            clean[key] = body[key]
    if "volume" in body:
        v = body["volume"]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 1:
            raise ValueError("Die Lautstärke muss zwischen 0 und 1 liegen.")
        clean["volume"] = float(v)
    return clean


def apply_settings(clean):
    if "trials" in clean:
        Settings.trials = clean["trials"]
    if "show_article" in clean:
        Settings.show_article = clean["show_article"]
    if "shuffle" in clean:
        Settings.shuffle_mode = clean["shuffle"]
    if "sound_enable" in clean:
        Settings.sound_enable = clean["sound_enable"]
    if "volume" in clean:
        Settings.volume_limit = clean["volume"]


def load_saved_settings():
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            apply_settings(parse_settings(json.load(f)))
    except (OSError, ValueError):
        pass  # no file yet, or unreadable/invalid: keep the defaults from main_settings.py


load_saved_settings()


@app.get("/api/settings")
def get_settings():
    return jsonify(current_settings())


@app.post("/api/settings")
def update_settings():
    body = request.get_json(force=True, silent=True) or {}
    try:
        clean = parse_settings(body)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    apply_settings(clean)
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(current_settings(), f, indent=2)
    except OSError:
        pass  # still applied for this run
    return jsonify(current_settings())


@app.get("/sound/<path:filename>")
def sound_file(filename):
    """Serve the project's mp3s so the browser can play them."""
    return send_from_directory(os.path.join(REPO_ROOT, "sound"), filename)


@app.get("/api/chapters")
def get_chapters():
    return jsonify({
        "chapters": [
            {"number": n, "count": len(CHAPTERS[n])}
            for n in sorted(CHAPTERS.keys())
        ]
    })


@app.get("/api/chapters/<int:chapter_number>")
def get_chapter(chapter_number):
    vocab = CHAPTERS.get(chapter_number)
    if vocab is None:
        return jsonify({"error": "Chapter not found"}), 404
    return jsonify({"chapter": chapter_number, "words": vocabulary_to_json(vocab)})


@app.get("/api/search")
def search():
    q = request.args.get("q", "").strip().lower()
    if not q:
        return jsonify({"query": q, "results": []})
    results = []
    for num in sorted(CHAPTERS.keys()):
        for word in vocabulary_to_json(CHAPTERS[num]):
            if q in word["en"].lower() or any(q in g.lower() for g in word["de"]):
                results.append({"chapter": num, **word})
    return jsonify({"query": q, "results": results[:60]})


@app.get("/api/verbs")
def get_verbs():
    return jsonify({"verbs": verbs})


# ---------------------------------------------------------------- Englisch -> Deutsch round ----

@app.post("/api/round/start")
def round_start():
    body = request.get_json(force=True) or {}
    chapter_numbers = body.get("chapters") or list(CHAPTERS.keys())
    start, end = body.get("start"), body.get("end")

    raw_vocab = merge_chapters(chapter_numbers)
    start, end, err = check_range(len(raw_vocab), start, end)
    if err:
        return err
    raw_vocab = apply_range_filter(raw_vocab, start, end)  # real function, untouched

    vocab_pairs, remaining = build_vocab_pairs(raw_vocab)
    session_id = str(uuid.uuid4())
    SESSIONS[session_id] = {
        "vocab_pairs": vocab_pairs,
        "remaining": remaining,
        "completed": set(),
        "correct_answers": 0,
        "total_attempts": 0,
        "practice_words": [],
        "error_analyzer": ErrorAnalyzer(),  # real class
        "current": None,
        "history": [],  # ordered list of completed english-tuples, for the "Bisherige Wörter" review
    }
    return jsonify({"session_id": session_id, "total_words": len(remaining)})


def mark_completed(session, cur):
    session["completed"].add(cur["random_engs"])
    session["history"].append(cur["random_engs"])
    cur["done"] = True  # blocks a second /api/round/answer for this word (double submit)


@app.post("/api/round/next")
def round_next():
    body = request.get_json(force=True) or {}
    session = SESSIONS.get(body.get("session_id"))
    if session is None:
        return jsonify({"error": "unknown session"}), 404

    if len(session["completed"]) == len(session["remaining"]):
        total = session["total_attempts"]
        rate = round((session["correct_answers"] / total) * 100, 2) if total else 0
        fb = German_feedback(rate, session["correct_answers"], total)  # real class

        # Mirrors main.py lines 335-338: group the real ErrorAnalyzer log by
        # error_type, sorted by frequency, each with a value_counts() of the
        # actual missed words — same computation, just returned as JSON here
        # instead of printed to a terminal.
        error_summary = []
        analyzer_data = session["error_analyzer"].data
        if len(analyzer_data) > 0:
            grouped = analyzer_data.groupby("error_type")
            for err_type, group in sorted(grouped, key=lambda x: len(x[1]), reverse=True):
                error_summary.append({
                    "error_type": err_type,
                    "count": len(group),
                    "words": [{"word": word, "count": int(n)} for word, n in group["correct_answer"].value_counts().items()],
                })

        return jsonify({
            "done": True,
            "congrats_msg": German_feedback.congrats_msg,
            "result_line": fb.Erfolgsquote(),
            "all_complete": German_feedback.all_complete if int(rate) == 100 else None,
            "practice_head": German_feedback.practice_head if session["practice_words"] else None,
            "practice_words": session["practice_words"],
            "error_summary": error_summary,
        })

    random_engs = pick_next_word(session["remaining"], session["completed"])  # real function
    display_eng = " / ".join(random_engs)
    german_words = [ger for eng, ger in session["vocab_pairs"] if eng == random_engs]
    word_label = "deutsches Wort" if len(german_words) == 1 else "deutsche Wörter"  # from main.py

    session["current"] = {
        "random_engs": random_engs, "german_words": german_words,
        "guessed": set(), "wrong_guesses": 0, "awaiting_article": None, "done": False,
    }
    return jsonify({
        "done": False,
        "display_eng": display_eng,
        "word_count": len(german_words),
        "intro": f"Es gibt {len(german_words)} {word_label}.",
        "progress": {"completed": len(session["completed"]), "total": len(session["remaining"])},
    })


@app.post("/api/round/answer")
def round_answer():
    body = request.get_json(force=True) or {}
    session = SESSIONS.get(body.get("session_id"))
    if session is None or session["current"] is None:
        return jsonify({"error": "no active round"}), 404
    cur = session["current"]
    if cur.get("done"):
        # Already answered (e.g. a second Enter/click sent before the "next word"
        # step ran) — ignore it instead of counting it again.
        return jsonify({"result": "duplicate", "message": "Diese Runde ist bereits abgeschlossen.",
                         "round_complete": True})
    analyzer = session["error_analyzer"]
    answer = (body.get("answer") or "").lower().strip()
    session["total_attempts"] += 1

    german_words = cur["german_words"]

    # blank answer — mirrors main.py lines 100-116
    if answer == "":
        closest = analyzer.closest_term(answer, german_words)  # real ErrorAnalyzer
        analyzer.log_error(answer, closest)
        cur["wrong_guesses"] += 1
        return _wrong_or_reveal(session, cur)

    for ger in german_words:
        if ger in cur["guessed"]:
            continue
        correct_article, correct_word = split_article(ger)

        if answer == ger.lower().strip() or (correct_article and answer == correct_word):
            if Settings.show_article and correct_article and answer == correct_word:
                cur["awaiting_article"] = ger
                return jsonify({"result": "needs_article", "message": Quiz_eng_ger.right_ans,
                                 "prompt": Quiz_eng_ger.enter_right_article})
            session["correct_answers"] += 1
            cur["guessed"].add(ger)
            if len(cur["guessed"]) >= len(german_words):
                mark_completed(session, cur)
            return jsonify({
                "result": "correct", "message": Quiz_eng_ger.right_ans,
                "word": ger, "round_complete": len(cur["guessed"]) >= len(german_words),
            })

    # no match — mirrors main.py lines 156-175
    closest = analyzer.closest_term(answer, german_words)  # real ErrorAnalyzer
    analyzer.log_error(answer, closest)
    cur["wrong_guesses"] += 1
    return _wrong_or_reveal(session, cur)


def _wrong_or_reveal(session, cur):
    remaining_unguessed = [g for g in cur["german_words"] if g not in cur["guessed"]]
    if cur["wrong_guesses"] >= Settings.trials:
        for g in remaining_unguessed:
            session["practice_words"].append(g)
        session["practice_words"].append(" ")
        cur["guessed"] = set(cur["german_words"])
        mark_completed(session, cur)
        return jsonify({
            "result": "revealed", "message": Quiz_eng_ger.wrong_ans,
            "incorrect_head": Quiz_eng_ger.incorrect_head,
            "correct_head": Quiz_eng_ger.correct_head,
            "words": remaining_unguessed, "round_complete": True,
            "wrong_guesses": cur["wrong_guesses"], "trials": Settings.trials,
        })
    return jsonify({
        "result": "wrong", "message": Quiz_eng_ger.wrong_ans,
        "wrong_guesses": cur["wrong_guesses"], "trials": Settings.trials,
        "round_complete": False,
    })


@app.post("/api/round/history")
def round_history():
    """Every word the session has already gone through, in order, with the
    real German forms and whether it ended up in practice_words (i.e. was
    ever missed) — for the 'Bisherige Wörter' review button."""
    body = request.get_json(force=True) or {}
    session = SESSIONS.get(body.get("session_id"))
    if session is None:
        return jsonify({"error": "unknown session"}), 404

    entries = []
    for eng in session["history"]:
        german_words = [ger for e, ger in session["vocab_pairs"] if e == eng]
        missed = any(g in session["practice_words"] for g in german_words)
        entries.append({"en": " / ".join(eng), "de": german_words, "missed": missed})
    return jsonify({"history": entries})


@app.post("/api/round/article")
def round_article():
    body = request.get_json(force=True) or {}
    session = SESSIONS.get(body.get("session_id"))
    if session is None or session["current"] is None or not session["current"]["awaiting_article"]:
        return jsonify({"error": "no article pending"}), 404
    cur = session["current"]
    ger = cur.pop("awaiting_article")
    article = (body.get("article") or "").lower().strip()
    correct_article, correct_word = split_article(ger)

    msg_obj = Quiz_eng_ger(ger)  # real class, real instance
    if article == correct_article:
        session["correct_answers"] += 1
        message = msg_obj.artikel_ist_richtig()
        correct = True
    else:
        session["error_analyzer"].log_error(f"{article} {correct_word}", ger)
        message = msg_obj.artikel_ist_falsch()
        correct = False

    cur["guessed"].add(ger)
    round_complete = len(cur["guessed"]) >= len(cur["german_words"])
    if round_complete:
        mark_completed(session, cur)
    return jsonify({"result": "correct" if correct else "wrong", "message": message,
                     "round_complete": round_complete})


# ---------------------------------------------------------------- Deutsch -> Englisch round ----
#
# Mirrors quiz_ger_eng() in main.py exactly:
#   - the prompt is the German word(s) (all synonyms for the chapter entry)
#   - the user only needs to type ONE matching English term to pass the round
#     (unlike Englisch -> Deutsch, there is no per-synonym slot to fill)
#   - Settings.trials, ErrorAnalyzer.closest_term/log_error and the real
#     Quiz_ger_eng / Eng_feedback message classes decide everything; this
#     file only flattens the for/else loop into stateless request/response
#     steps and serializes the result to JSON.

@app.post("/api/round2/start")
def round2_start():
    body = request.get_json(force=True) or {}
    chapter_numbers = body.get("chapters") or list(CHAPTERS.keys())
    start, end = body.get("start"), body.get("end")

    raw_vocab = merge_chapters(chapter_numbers)
    start, end, err = check_range(len(raw_vocab), start, end)
    if err:
        return err
    raw_vocab = apply_range_filter(raw_vocab, start, end)  # real function, untouched

    vocab_pairs, remaining = build_vocab_pairs(raw_vocab)
    session_id = str(uuid.uuid4())
    SESSIONS2[session_id] = {
        "vocab_pairs": vocab_pairs,
        "remaining": remaining,
        "completed": set(),
        "correct_answers": 0,
        "total_attempts": 0,
        "practice_words": [],
        "error_analyzer": ErrorAnalyzer(),  # real class
        "current": None,
        "history": [],  # ordered list of completed english-tuples, for "Bisherige Wörter"
    }
    return jsonify({"session_id": session_id, "total_words": len(remaining)})


def mark_completed2(session, cur):
    session["completed"].add(cur["random_engs"])
    session["history"].append(cur["random_engs"])
    cur["done"] = True  # blocks a second /api/round2/answer for this word (double submit)


@app.post("/api/round2/next")
def round2_next():
    body = request.get_json(force=True) or {}
    session = SESSIONS2.get(body.get("session_id"))
    if session is None:
        return jsonify({"error": "unknown session"}), 404

    if len(session["completed"]) == len(session["remaining"]):
        total = session["total_attempts"]
        rate = round((session["correct_answers"] / total) * 100, 2) if total else 0
        fb = Eng_feedback(rate, session["correct_answers"], total)  # real class

        # Mirrors main.py's error_analyzer summary — same computation as the
        # Englisch -> Deutsch results, just returned as JSON here.
        error_summary = []
        analyzer_data = session["error_analyzer"].data
        if len(analyzer_data) > 0:
            grouped = analyzer_data.groupby("error_type")
            for err_type, group in sorted(grouped, key=lambda x: len(x[1]), reverse=True):
                error_summary.append({
                    "error_type": err_type,
                    "count": len(group),
                    "words": [{"word": word, "count": int(n)} for word, n in group["correct_answer"].value_counts().items()],
                })

        return jsonify({
            "done": True,
            "congrats_msg": Eng_feedback.congrats_msg,
            "result_line": fb.success_rate(),
            "all_complete": Eng_feedback.all_complete if int(rate) == 100 else None,
            "practice_head": Eng_feedback.practice_head if session["practice_words"] else None,
            "practice_words": session["practice_words"],
            "error_summary": error_summary,
        })

    random_engs = pick_next_word(session["remaining"], session["completed"])  # real function
    german_words = [ger for eng, ger in session["vocab_pairs"] if eng == random_engs]
    display_de = ", ".join(german_words)

    session["current"] = {"random_engs": random_engs, "german_words": german_words, "wrong_guesses": 0, "done": False}
    return jsonify({
        "done": False,
        "display_de": display_de,
        "intro": "📘 Enter the appropriate English word",
        "progress": {"completed": len(session["completed"]), "total": len(session["remaining"])},
    })


@app.post("/api/round2/answer")
def round2_answer():
    body = request.get_json(force=True) or {}
    session = SESSIONS2.get(body.get("session_id"))
    if session is None or session["current"] is None:
        return jsonify({"error": "no active round"}), 404
    cur = session["current"]
    if cur.get("done"):
        return jsonify({"result": "duplicate", "message": "Diese Runde ist bereits abgeschlossen.",
                         "round_complete": True})
    analyzer = session["error_analyzer"]
    random_engs = cur["random_engs"]
    answer = (body.get("answer") or "").lower().strip()
    session["total_attempts"] += 1

    # blank answer — mirrors main.py lines 61-66 (no incorrect_attempts message on blanks)
    if answer == "":
        closest = analyzer.closest_term(answer, random_engs)  # real ErrorAnalyzer
        analyzer.log_error(answer, closest)
        cur["wrong_guesses"] += 1
        return _wrong_or_reveal2(session, cur, attempts_message=None)

    if answer in accepted_english_set(random_engs):
        session["correct_answers"] += 1
        mark_completed2(session, cur)
        return jsonify({"result": "correct", "message": Quiz_ger_eng.right_ans, "round_complete": True})

    # wrong, non-blank — mirrors main.py lines 73-82
    closest = analyzer.closest_term(answer, random_engs)  # real ErrorAnalyzer
    analyzer.log_error(answer, closest)
    cur["wrong_guesses"] += 1
    attempts_message = Quiz_ger_eng(cur["wrong_guesses"] - 1).incorrect_attempts()
    return _wrong_or_reveal2(session, cur, attempts_message=attempts_message)


def _wrong_or_reveal2(session, cur, attempts_message):
    if cur["wrong_guesses"] >= Settings.trials:
        for g in cur["german_words"]:
            session["practice_words"].append(g)
        session["practice_words"].append(" ")
        mark_completed2(session, cur)
        return jsonify({
            "result": "revealed", "message": Quiz_ger_eng.wrong_ans,
            "incorrect_head": Quiz_ger_eng.incorrect_head,
            "correct_head": Quiz_ger_eng.correct_head,
            "display_eng": " / ".join(cur["random_engs"]),
            "words": cur["german_words"], "round_complete": True,
            "wrong_guesses": cur["wrong_guesses"], "trials": Settings.trials,
        })
    return jsonify({
        "result": "wrong", "message": Quiz_ger_eng.wrong_ans, "attempts_message": attempts_message,
        "wrong_guesses": cur["wrong_guesses"], "trials": Settings.trials, "round_complete": False,
    })


@app.post("/api/round2/history")
def round2_history():
    """Every word the mode-2 session has already gone through, in order,
    with the real German forms and whether it ended up in practice_words
    (i.e. was revealed after too many wrong guesses)."""
    body = request.get_json(force=True) or {}
    session = SESSIONS2.get(body.get("session_id"))
    if session is None:
        return jsonify({"error": "unknown session"}), 404

    entries = []
    for eng in session["history"]:
        german_words = [ger for e, ger in session["vocab_pairs"] if e == eng]
        missed = any(g in session["practice_words"] for g in german_words)
        entries.append({"en": " / ".join(eng), "de": german_words, "missed": missed})
    return jsonify({"history": entries})


from webapp.review_routes import review_bp  # mode 4 (review) — see that file. Imported here
app.register_blueprint(review_bp)             # (not at the top) so it can reuse check_range() above.

from webapp.audio_routes import audio_bp  # mode 5 (audio) — see that file.
app.register_blueprint(audio_bp)          # same reason as review_bp: needs check_range() to already exist.

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)