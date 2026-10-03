"""
Mode 3 (search) for the web app — added as a self-contained Blueprint so the
existing webapp/app.py, app.js, style.css and index.html are not touched
beyond the two lines needed to register it (see the bottom of this file).

Mirrors search_word() in modes_and_logics/logics.py exactly, including which
vocabulary it searches — all twelve chapters, same as mode 3 in main.py.

Each match now also reports which chapter it's from and its serial number
in that chapter, so a hit can be looked up in mode 4 (review). This means
searching chapter-by-chapter instead of the single merged dict search_word()
itself uses (`chapter_eleven | chapter_twelve | ... | chapter_seven`) — the
merge is a dict union, so for the 13 English terms that happen to repeat
across chapters it silently keeps only the last chapter's forms. Chapter-by-
chapter search has no such blind spot: a term repeated in two chapters now
comes back as two separate, correctly-numbered matches instead of one.

The offline part (search_word's two match loops) is untouched real-logic
re-use: no matching rule is redecided here, only how the vocabulary is
walked to keep chapter/serial-number provenance. The online-dictionary part
(Search_in_Pons in modes_and_logics/Search_Word.py) is interactive
(input()/print()), so it's flattened into JSON responses the same way
app.py already flattens quiz_eng_ger()/quiz_ger_eng() — same PONS endpoint,
same params, same status-code handling as PONSDictionary.translate().
"""
import os
import re

import requests
from flask import Blueprint, jsonify, request

from webapp.chapters_data import CHAPTERS_ALL  # shared with review_routes.py / audio_routes.py
from modes_and_logics.Search_Word import Search_in_Pons

search_bp = Blueprint("search", __name__, url_prefix="/api/search")

ARTICLES = ("der ", "die ", "das ")


def _local_search(term):
    """Same two match rules as search_word() in logics.py (an exact English
    term, or a German form / its bare-noun form), walked chapter by chapter
    so each hit can report {chapter, no} — "no" being the same serial number
    mode 4 (review) shows for that chapter, i.e. its 1-based position in
    that chapter's own list."""
    search = term.lower().strip()
    as_english = []  # search matched an English term -> that entry's German forms
    as_german = []   # search matched a German form (or its bare-noun form) -> the English terms + matched form

    for chapter_no, chapter_vocab in CHAPTERS_ALL.items():
        for i, (eng_terms, ger_list) in enumerate(chapter_vocab.items(), start=1):
            if any(search == e.lower().strip() for e in eng_terms):
                as_english.append({"chapter": chapter_no, "no": i, "english": list(eng_terms), "german": list(ger_list)})

            for ger in ger_list:
                bare = ger[4:].lower().strip() if ger[0:4].lower() in ARTICLES else None
                if search == ger.lower().strip() or (bare is not None and search == bare):
                    as_german.append({"chapter": chapter_no, "no": i, "matched_german": ger, "english": list(eng_terms)})

    return as_english, as_german


@search_bp.post("")
def search():
    body = request.get_json(force=True, silent=True) or {}
    term = (body.get("query") or "").strip()
    if not term:
        return jsonify({"error": "Bitte ein Wort eingeben."}), 400

    as_english, as_german = _local_search(term)
    return jsonify({
        "query": term,
        "found": bool(as_english or as_german),
        "as_english": as_english,  # searched an English term -> German translations
        "as_german": as_german,    # searched a German word -> English translations
    })


def _detect_language(text):
    return Search_in_Pons("dummy").detect_language(text)  # real, unmodified detection rule


def _pons_translate(word, source_lang):
    """Same request PONSDictionary.translate() makes, but returning the
    reason for a miss instead of printing it, so the frontend can show it."""
    api_key = os.getenv("PONS_API_KEY")
    if not api_key:
        return None, "PONS_API_KEY ist nicht gesetzt."
    try:
        resp = requests.get(
            "https://api.pons.com/v1/dictionary",
            headers={"X-Secret": api_key},
            params={"q": word, "l": "deen", "in": source_lang, "ref": "true", "language": "en"},
        )
    except requests.exceptions.RequestException as e:
        return None, f"Error: {e}"

    if resp.status_code == 204:
        return None, f"No results found for '{word}'"
    if resp.status_code == 403:
        return None, "Authentication failed (key not activated or daily limit reached)."
    if resp.status_code == 404:
        return None, "Dictionary not found"
    if resp.status_code == 503:
        return None, "Daily API limit reached (1000/month)"
    try:
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        return None, f"Error: {e}"
    return resp.json(), None


def _clean(text):
    return re.sub(r"<.*?>", "", text or "")


def _collect_pairs(word, results, max_results=3):
    """Same filtering as PONSDictionary.print_results(), collected into pairs
    instead of printed. Also returns how many translations PONS actually sent
    back before that <=2-word-source / <=3-word-target filter ran, so a "no
    pairs" outcome can be told apart from "PONS had nothing at all" in the
    terminal log (see search_online() below)."""
    pairs = []
    raw_count = 0
    for lang_result in results or []:
        for hit in lang_result.get("hits", []):
            if hit.get("type") != "entry":
                continue
            for rom in hit.get("roms", []):
                for arab in rom.get("arabs", []):
                    for trans in arab.get("translations", [])[:max_results]:
                        raw_count += 1
                        src = _clean(trans.get("source", ""))
                        tgt = _clean(trans.get("target", ""))
                        if len(src.split()) <= 2 and len(tgt.split()) <= 3:
                            pairs.append({"source": src, "target": tgt})
    return pairs, raw_count


@search_bp.post("/online")
def search_online():
    """source_lang: omit it first: an ambiguous word (no umlaut/ß, not a
    capitalized German-looking noun) comes back with ambiguous:true so the
    frontend can ask German->English or English->German, exactly like the
    CLI's `input("Translate from (1) German→English or (2) English→German? ")`.
    Pass source_lang ('de'|'en') once the user (or the auto-detect) has decided."""
    body = request.get_json(force=True, silent=True) or {}
    term = (body.get("query") or "").strip()
    if not term:
        return jsonify({"error": "Bitte ein Wort eingeben."}), 400

    source_lang = body.get("source_lang")
    if source_lang not in ("de", "en"):
        detected = _detect_language(term)
        if detected == "ambiguous":
            print(f"[mode 3 online] {term!r}: ambiguous, asking for a direction")
            return jsonify({"ambiguous": True, "query": term})
        source_lang = detected

    print(f"[mode 3 online] {term!r} source_lang={source_lang} -> calling PONS…")
    results, error = _pons_translate(term, source_lang)
    if error:
        print(f"[mode 3 online] {term!r} source_lang={source_lang} -> {error}")
        return jsonify({"query": term, "source_lang": source_lang, "found": False, "message": error})

    pairs, raw_count = _collect_pairs(term, results)
    if raw_count and not pairs:
        print(f"[mode 3 online] {term!r} source_lang={source_lang} -> PONS returned "
              f"{raw_count} translation(s), but all were filtered out (source >2 words "
              f"or target >3 words) -- that filter is the same one the CLI uses, so this "
              f"isn't new, but it means PONS *did* find something.")
    elif not raw_count:
        print(f"[mode 3 online] {term!r} source_lang={source_lang} -> PONS returned 0 translations.")
    else:
        print(f"[mode 3 online] {term!r} source_lang={source_lang} -> {len(pairs)} pair(s) shown.")

    return jsonify({
        "query": term, "source_lang": source_lang,
        "found": bool(pairs), "pairs": pairs,
        "message": None if pairs else "No direct simple translation found.",
    })