"""
"Wörter durchsehen" -> click a word pair -> Groq explains it. A self-contained Blueprint,
same pattern as search_routes.py / context_routes.py / verbs_routes.py / apikeys_routes.py.
Nothing existing is modified.

  POST /api/explain   {"chapter": 3, "german": ["beweisen", "nachweisen", ...], "refresh": false}

What happens
  1. The word group must be a real entry of the glossary (CHAPTERS_ALL). The English gloss comes
     from there, not from the browser. This also means the endpoint cannot be used as a general
     chat proxy with your Groq key.
  2. Groq (same model + key as description_ai.py) gets the teaching brief below and answers with
     ONE JSON object: per-word explanations, a "how to choose" guide, a memory summary and a
     multiple-choice quiz. The quiz is returned with the answers, but the page only reveals them
     after you have picked an option.
  3. The answer is validated/cleaned (a model can return odd JSON) and saved in
     webapp/explain_cache.json, so opening the same pair again is instant and costs no tokens.
     "Neu erstellen" in the page sends refresh=true to ask Groq again.
"""
import json
import os
import random
import re
import tempfile
import threading
from urllib.parse import urlparse

import groq
from flask import Blueprint, jsonify, request

from webapp.chapters_data import CHAPTERS_ALL
from webapp.review_routes import _capitalized_noun  # same noun-capitalisation the review list shows

explain_bp = Blueprint("explain", __name__, url_prefix="/api/explain")

MODEL = "openai/gpt-oss-20b"      # same model description_ai.py uses; try "openai/gpt-oss-120b" for richer answers
SCHEMA_VERSION = 1                # bump when the prompt/JSON shape changes -> old cache entries are ignored
CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "explain_cache.json")
_cache_lock = threading.Lock()

MAX_WORDS = 12

_PROMPT_CORE = """You are an expert, patient teacher of German for English-speaking learners at B1-B2 level.
The learner wants to understand the differences between similar German words, especially words with related meanings that are used in different contexts. Teach them how to CHOOSE the correct word when speaking or writing German, not just to memorise translations. Focus on meaning, context, typical sentence patterns and natural usage.

You get one word group from their textbook glossary. Explain EVERY word of the group separately, and in this order, with these parts:
- the German word and its most accurate English meaning
- its specific context of use: when, why and in what situations Germans use it
- a simple explanation of how it differs from the other words of the group (or from similar words)
- two or three natural German example sentences, each with an English translation
- a short memory trick or rule that helps to remember when to use it
- important grammar patterns, fixed expressions and common collocations
- common mistakes learners make with it

Style rules:
- Practical and easy to understand. Simple English, as if teaching B1-B2. Do not just give dictionary definitions: explain the practical difference in real-life usage.
- Say clearly whether two words are interchangeable, or whether swapping one for another changes the meaning, sounds unnatural, or is grammatically wrong. Mention register (formal, written, spoken, legal, everyday) when it matters.
- If a word has several important meanings, explain the most important ones separately (other_meanings).
- Use everyday situations and examples from work, studies, conversations and life in Germany where appropriate.
- Explain subtle differences without linguistic jargon.

Accuracy rules (very important):
- Only state things you are confident about. Never invent collocations, rules or usage. If a nuance is uncertain, say so briefly.
- German example sentences must be natural and grammatically correct (cases, prepositions, word order, separable prefixes, Perfekt auxiliary, noun gender and plural). Nouns come with their article.
- If the group contains only ONE word, there are no synonyms in the list: still fill every part, and in "difference" compare it with its 1-3 closest similar German words (put those in the sentence, they do not need their own entry)."""

_QUIZ_RULES = """Quiz rules:
- Realistic German sentences (work, studies, daily life) with ONE blank written as ____ .
- 4 options per question. Prefer the words of the group as options (they are the confusable ones); if the group has fewer than 4 words, add plausible similar German words. Options must already be in the correct form for the blank (conjugated, with article, etc.).
- Exactly one best answer per question. "answer" must be the EXACT text of the correct option. Do not hint at the answer in the question.
- "explanation": why the correct option is right AND why the other options do not fit or sound less natural.
- "translation": English translation of the complete sentence with the correct word filled in."""

_OUTPUT_HEAD = """OUTPUT FORMAT: return ONLY one valid JSON object, no markdown code fences, no text before or after it. String values are plain text; you may wrap a key German word in **double asterisks** for bold, nothing else (no headings, no bullet characters). All explanations are in English; all example sentences are German with English translations."""

_SCHEMA = """{
  "overview": "1-3 sentences: what these words have in common and the main split between them",
  "words": [
    {
      "german": "the word exactly as given",
      "english": "most accurate short English meaning",
      "context": "when, why and in what situations it is used (2-4 sentences)",
      "other_meanings": [ {"meaning": "other important meaning", "explanation": "short explanation"} ],
      "difference": "how it differs from the other words; interchangeable or not (2-5 sentences)",
      "examples": [ {"de": "German sentence", "en": "English translation"} ],
      "memory_trick": "one short memorable rule or image",
      "grammar": [ "grammar pattern / fixed expression / collocation", "..." ],
      "mistakes": [ "common learner mistake and the fix", "..." ]
    }
  ],
  "how_to_choose": [ "3-5 short decision rules for choosing the right word" ],
  "summary": [ {"word": "German word", "use_when": "very short: use it when ..."} ]__QUIZ__
}
Use [] for other_meanings when the word has no other important meaning."""

_SCHEMA_QUIZ = ''',
  "quiz": [
    {"question": "German sentence with ____", "options": ["a", "b", "c", "d"], "answer": "exact text of the correct option", "explanation": "...", "translation": "..."}
  ]'''

_QUIZ_ONLY_INTRO = """You are an expert, patient teacher of German for English-speaking learners at B1-B2 level. The learner has just read an explanation of a German word group (summarised in the user message) and now wants a practice quiz that tests whether they can CHOOSE the right word."""

_QUIZ_ONLY_FORMAT = """OUTPUT FORMAT: return ONLY one valid JSON object, no markdown code fences, no text before or after it. Plain text only; you may wrap a key German word in **double asterisks**.
{
  "quiz": [
    {"question": "German sentence with ____", "options": ["a", "b", "c", "d"], "answer": "exact text of the correct option", "explanation": "...", "translation": "..."}
  ]
}"""


def _system_prompt(with_quiz):
    """The teaching brief. Without the quiz, the quiz rules and the quiz part of the JSON are left
    out, so Groq neither reads nor writes them (fewer tokens)."""
    parts = [_PROMPT_CORE]
    if with_quiz:
        parts.append(_QUIZ_RULES)
    parts.append(_OUTPUT_HEAD)
    parts.append(_SCHEMA.replace("__QUIZ__", _SCHEMA_QUIZ if with_quiz else ""))
    return "\n\n".join(parts)


def _quiz_only_prompt():
    return "\n\n".join([_QUIZ_ONLY_INTRO, _QUIZ_RULES, _QUIZ_ONLY_FORMAT])


# --------------------------------------------------------------------------- request checks --

@explain_bp.before_request
def _same_origin_only():
    """The app has CORS(app) wide open. Without this, any website open in the same browser could
    spend your Groq quota through http://127.0.0.1:5000. Browsers always send Origin on
    cross-site requests, so a mismatch is refused."""
    origin = request.headers.get("Origin")
    if origin and urlparse(origin).netloc != request.host:
        return jsonify({"error": "Anfrage von fremder Herkunft abgelehnt.", "code": "origin"}), 403


def _api_key():
    v = (os.environ.get("GROQ_API_KEY") or "").strip()
    if not v or (v.lower().startswith("your_") and v.lower().endswith("_here")):
        return ""
    return v


def _find_entry(chapter, words):
    """Look the word group up in the glossary (case-insensitive, same order).
    Returns (chapter, english_terms, german_words) or None."""
    wanted = [w.casefold() for w in words]
    order = [chapter] + [c for c in CHAPTERS_ALL if c != chapter] if chapter in CHAPTERS_ALL else list(CHAPTERS_ALL)
    for ch in order:
        for eng_terms, ger_list in CHAPTERS_ALL[ch].items():
            if [g.casefold() for g in ger_list] == wanted:
                return ch, list(eng_terms), [_capitalized_noun(g) for g in ger_list]
    return None


# --------------------------------------------------------------------------------- cache --

def _cache_key(words):
    return f"v{SCHEMA_VERSION}|{MODEL}|" + "|".join(w.casefold() for w in words)


def _cache_read():
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _cache_write(key, value):
    """Best effort: a failing cache must never break the explanation itself."""
    with _cache_lock:
        data = _cache_read()
        data[key] = value
        directory = os.path.dirname(CACHE_PATH) or "."
        try:
            fd, tmp = tempfile.mkstemp(prefix=".explain.", dir=directory)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)
                os.replace(tmp, CACHE_PATH)
            except BaseException:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise
        except OSError:
            pass


# ----------------------------------------------------------------------------------- Groq --

def _make_client():
    return groq.Groq(api_key=_api_key(), timeout=90.0, max_retries=1)  # tests replace this


def _call_groq(messages, max_tokens):
    """Returns the raw text. JSON mode + low reasoning effort are nice-to-have: if the model
    or SDK rejects them we retry once without."""
    client = _make_client()
    base = dict(model=MODEL, messages=messages, temperature=0.4, max_completion_tokens=max_tokens)
    try:
        result = client.chat.completions.create(
            **base, response_format={"type": "json_object"}, reasoning_effort="low")
    except groq.BadRequestError:
        result = client.chat.completions.create(**base)
    choice = result.choices[0]
    text = (choice.message.content or "").strip()
    if getattr(choice, "finish_reason", None) == "length":
        print("⚠️ explain: Groq answer was cut off (max tokens reached)")
    return text


def _parse_json(text):
    """Model output -> dict. Tolerates ```json fences and text around the object."""
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.IGNORECASE)
    try:
        return json.loads(t)
    except ValueError:
        pass
    a, b = t.find("{"), t.rfind("}")
    if a != -1 and b > a:
        try:
            return json.loads(t[a:b + 1])
        except ValueError:
            return None
    return None


# ------------------------------------------------------------------------------ cleaning --

def _s(x, limit=1500):
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        x = str(x)
    return x.strip()[:limit] if isinstance(x, str) else ""


def _list(x, limit=8, item_limit=700):
    if isinstance(x, str):
        x = [x]
    if not isinstance(x, list):
        return []
    return [s for s in (_s(i, item_limit) for i in x) if s][:limit]


def _clean_word(w):
    if not isinstance(w, dict):
        return None
    examples = []
    for ex in (w.get("examples") if isinstance(w.get("examples"), list) else [])[:4]:
        if isinstance(ex, dict):
            de, en = _s(ex.get("de") or ex.get("german"), 400), _s(ex.get("en") or ex.get("english"), 400)
            if de:
                examples.append({"de": de, "en": en})
    others = []
    for m in (w.get("other_meanings") if isinstance(w.get("other_meanings"), list) else [])[:4]:
        if isinstance(m, dict) and _s(m.get("meaning"), 200):
            others.append({"meaning": _s(m.get("meaning"), 200), "explanation": _s(m.get("explanation"), 700)})
    out = {
        "german": _s(w.get("german"), 120),
        "english": _s(w.get("english"), 300),
        "context": _s(w.get("context")),
        "other_meanings": others,
        "difference": _s(w.get("difference")),
        "examples": examples,
        "memory_trick": _s(w.get("memory_trick"), 700),
        "grammar": _list(w.get("grammar")),
        "mistakes": _list(w.get("mistakes")),
    }
    if not (out["context"] or out["difference"] or out["examples"]):
        return None
    return out


def _clean_question(q):
    if not isinstance(q, dict):
        return None
    question = _s(q.get("question"), 500)
    options, seen = [], set()
    for o in (q.get("options") if isinstance(q.get("options"), list) else []):
        o = _s(o, 120)
        if o and o.casefold() not in seen:
            seen.add(o.casefold())
            options.append(o)
    if not question or not (2 <= len(options) <= 6):
        return None

    ans = q.get("answer")
    idx = None
    if isinstance(ans, str):
        a = ans.strip()
        for i, o in enumerate(options):                 # normal case: exact option text
            if o.casefold() == a.casefold():
                idx = i
                break
        if idx is None and len(a) == 1 and a.upper() in "ABCDEF" and ord(a.upper()) - 65 < len(options):
            idx = ord(a.upper()) - 65                   # model answered with a letter
    if idx is None:
        return None                                     # can't tell which option is right -> drop the question

    correct = options[idx]
    random.shuffle(options)                             # models like to put the answer in the same slot
    return {
        "question": question,
        "options": options,
        "answer": options.index(correct),
        "explanation": _s(q.get("explanation"), 1200),
        "translation": _s(q.get("translation"), 500),
    }


def _clean_quiz(raw):
    return [c for c in (_clean_question(q) for q in (raw if isinstance(raw, list) else [])[:10]) if c]


def _clean(data, words):
    """Raw model JSON -> the exact shape the page expects, or None if unusable."""
    if not isinstance(data, dict):
        return None
    raw_words = data.get("words") if isinstance(data.get("words"), list) else []
    cleaned = [c for c in (_clean_word(w) for w in raw_words[:MAX_WORDS]) if c]
    if not cleaned:
        return None
    if len(cleaned) == len(words):                      # keep the glossary spelling (nouns capitalised)
        for c, w in zip(cleaned, words):
            c["german"] = w
    summary = []
    for s in (data.get("summary") if isinstance(data.get("summary"), list) else [])[:MAX_WORDS]:
        if isinstance(s, dict) and _s(s.get("word"), 120):
            summary.append({"word": _s(s.get("word"), 120), "use_when": _s(s.get("use_when"), 400)})
    quiz = _clean_quiz(data.get("quiz"))
    return {
        "overview": _s(data.get("overview"), 900),
        "words": cleaned,
        "how_to_choose": _list(data.get("how_to_choose"), limit=6),
        "summary": summary,
        "quiz": quiz,
    }


# ------------------------------------------------------------------------------- route ----

def _error(message, code, status):
    return jsonify({"error": message, "code": code}), status


def _ask(messages, max_tokens):
    """Groq call -> (text, None) or (None, (message, code, status)). Shared by the explanation and the quiz top-up."""
    try:
        return _call_groq(messages, max_tokens), None
    except groq.AuthenticationError:
        return None, ("Der GROQ_API_KEY wurde abgelehnt. Prüfe ihn unter Einstellungen.", "bad_key", 401)
    except groq.RateLimitError:
        return None, ("Groq-Limit erreicht (zu viele Anfragen oder Tokens). Warte kurz und versuche es erneut.", "rate_limit", 429)
    except (groq.APIConnectionError, groq.APITimeoutError):
        return None, ("Keine Verbindung zu Groq. Internet prüfen und erneut versuchen.", "connection", 503)
    except groq.APIStatusError as e:
        print(f"⚠️ explain: Groq status {getattr(e, 'status_code', '?')}")
        return None, ("Groq hat einen Fehler gemeldet. Bitte erneut versuchen.", "groq_error", 502)


def _n_questions(n_words):
    return max(4, min(8, n_words + 3))


def _reply(data, cached, chapter, german, english, **extra):
    return jsonify({"data": data, "cached": cached, "chapter": chapter, "german": german, "english": english, **extra})


@explain_bp.post("")
def explain():
    """Body: {"chapter", "german": [...], "refresh": bool, "quiz": bool}
    quiz=false -> the quiz is not requested from Groq at all (fewer tokens). If a saved explanation
    already has a quiz it is returned anyway (it costs nothing); the page decides whether to show it.
    quiz=true and the saved explanation has no quiz yet -> only the quiz is requested and merged
    into the saved entry; the explanation is not generated again."""
    body = request.get_json(force=True, silent=True) or {}
    words = body.get("german")
    if (not isinstance(words, list) or not 1 <= len(words) <= MAX_WORDS
            or not all(isinstance(w, str) and 0 < len(w.strip()) <= 80 for w in words)):
        return _error("Ungültiges Wortpaar.", "bad_request", 400)
    words = [w.strip() for w in words]
    chapter = body.get("chapter") if isinstance(body.get("chapter"), int) else None
    want_quiz = body.get("quiz") is not False      # default True: older callers keep working

    found = _find_entry(chapter, words)
    if not found:
        return _error("Dieses Wortpaar steht nicht im Glossar.", "bad_request", 400)
    chapter, english, german = found

    key = _cache_key(german)
    hit = None if body.get("refresh") is True else _cache_read().get(key)
    if not (isinstance(hit, dict) and hit.get("words")):
        hit = None

    if hit and (not want_quiz or hit.get("quiz")):
        return _reply(hit, True, chapter, german, english)

    if not hit and not _api_key():
        return _error("GROQ_API_KEY fehlt. Trage ihn unter Einstellungen ein.", "no_key", 400)

    # ---- saved explanation without a quiz, quiz wanted now: ask for the quiz only -------------------------
    # If that fails the explanation is still returned (HTTP 200) with quiz_error, so the page can show
    # the explanation and put the problem inside the quiz block only.
    if hit:
        def quiz_problem(message, code):
            return _reply(hit, True, chapter, german, english, quiz_error={"message": message, "code": code})

        if not _api_key():
            return quiz_problem("GROQ_API_KEY fehlt. Trage ihn unter Einstellungen ein.", "no_key")
        brief = "\n".join(
            f"- {w['german']} ({w['english']}): {(w['difference'] or w['context'])[:350]}" for w in hit["words"])
        messages = [
            {"role": "system", "content": _quiz_only_prompt()},
            {"role": "user", "content": (
                f"German word group from the textbook glossary: {', '.join(german)}\n"
                f"Textbook English gloss: {', '.join(english)}\n"
                f"What the learner just read about each word:\n{brief}\n"
                f"Number of quiz questions: {_n_questions(len(german))}\n"
                "Return the JSON object now.")},
        ]
        text, err = _ask(messages, 2500)
        if err:
            return quiz_problem(err[0], err[1])
        parsed = _parse_json(text)
        quiz = _clean_quiz(parsed.get("quiz") if isinstance(parsed, dict) else None)
        if not quiz:
            print("⚠️ explain: could not use Groq quiz answer (invalid JSON or no valid questions)")
            return quiz_problem("Das Quiz konnte nicht erstellt werden. Bitte erneut versuchen.", "quiz_failed")
        hit = dict(hit, quiz=quiz)
        _cache_write(key, hit)
        return _reply(hit, True, chapter, german, english, quiz_added=True)

    # ---- nothing saved yet: explanation (+ quiz only if wanted) ------------------------------------------------
    user = (f"German word group from the textbook glossary: {', '.join(german)}\n"
            f"Textbook English gloss: {', '.join(english)}\n"
            f"Number of words in the group: {len(german)}\n")
    if want_quiz:
        user += f"Number of quiz questions: {_n_questions(len(german))}\n"
    else:
        user += "Do not write a quiz.\n"
    user += "Return the JSON object now."
    messages = [{"role": "system", "content": _system_prompt(want_quiz)}, {"role": "user", "content": user}]
    max_tokens = min(14000, (4500 if want_quiz else 3000) + 1100 * len(german))

    text, err = _ask(messages, max_tokens)
    if err:
        return _error(*err)
    cleaned = _clean(_parse_json(text), german)
    if not cleaned:
        print("⚠️ explain: could not use Groq answer (invalid JSON or empty)")
        return _error("Die KI-Antwort war nicht lesbar. Bitte erneut versuchen.", "bad_response", 502)
    if not want_quiz:
        cleaned["quiz"] = []                       # never keep a quiz nobody asked for

    _cache_write(key, cleaned)
    return _reply(cleaned, False, chapter, german, english)