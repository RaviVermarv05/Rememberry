"""
Mode 4 (review) for the web app — a self-contained Blueprint, same pattern as
search_routes.py (mode 3): webapp/app.py only gains the two lines needed to
register it (added near the bottom of that file, after check_range() is
defined, so this can import that real function instead of re-implementing
the same range check a third time).

Mirrors review() in modes_and_logics/logics.py exactly: same chapter dict,
same noun-capitalization rule for the German column, same
apply_range_filter(). Unlike modes 1-3, review always works on ONE chapter
at a time, exactly like the CLI ("Enter chapter number 1-12 ") — there is no
multi-chapter merge here.
"""
from flask import Blueprint, jsonify, request

from Data.word_list import (
    chapter_one, chapter_two, chapter_three, chapter_four, chapter_five,
    chapter_six, chapter_seven, chapter_eight, chapter_nine, chapter_ten,
    chapter_eleven, chapter_twelve,
)
from modes_and_logics.logics import apply_range_filter
from webapp.range_check import check_range  # same helper app.py uses — no second copy of this logic

review_bp = Blueprint("review", __name__, url_prefix="/api/review")

# Same 12-chapter dict as `chapters = {1: chapter_one, ...}` in main.py
CHAPTERS_ALL = {
    1: chapter_one, 2: chapter_two, 3: chapter_three, 4: chapter_four,
    5: chapter_five, 6: chapter_six, 7: chapter_seven, 8: chapter_eight,
    9: chapter_nine, 10: chapter_ten, 11: chapter_eleven, 12: chapter_twelve,
}


def _capitalized_noun(word):
    """Exactly review()'s rule in logics.py: article stays lower-case, the
    noun itself gets capitalized; anything without an article is untouched."""
    if word[0:4].lower() in ("der ", "die ", "das "):
        return word[0:3].lower().strip() + word[3] + word[4].capitalize() + word[5:].lower()
    return word


@review_bp.post("")
def review():
    body = request.get_json(force=True, silent=True) or {}
    chapter = body.get("chapter")
    if not isinstance(chapter, int) or chapter not in CHAPTERS_ALL:
        return jsonify({"error": "Bitte ein Kapitel von 1 bis 12 wählen."}), 400

    chapter_vocab = CHAPTERS_ALL[chapter]
    total = len(chapter_vocab)

    start, end, err = check_range(total, body.get("start"), body.get("end"))  # real function, untouched
    if err:
        return err
    if start is not None:
        chapter_vocab = apply_range_filter(chapter_vocab, start, end)  # real function, untouched

    entries = [
        {"no": i, "german": ", ".join(_capitalized_noun(g) for g in ger_list), "english": ", ".join(eng_terms)}
        for i, (eng_terms, ger_list) in enumerate(chapter_vocab.items(), start=1)
    ]
    return jsonify({
        "chapter": chapter, "total": total,
        "range": {"start": start, "end": end} if start is not None else None,
        "entries": entries,
    })