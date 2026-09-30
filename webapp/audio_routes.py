"""
Mode 5 (audio) for the web app — a self-contained Blueprint, same pattern as
search_routes.py (mode 3) and review_routes.py (mode 4): webapp/app.py only
gains the two lines needed to register it.

Mirrors the audio-generation half of mode 5 in main.py exactly: same chapter
dict, same check_range()/apply_range_filter() (from webapp/range_check.py and
modes_and_logics/logics.py — real functions, not re-implemented), same
logics.schuflle(), same create_mp3_en_de()/create_mp3_de_en() from
modes_and_logics/speech_output.py, and the same "vocab {chapter}_en_de.mp3" /
"vocab {chapter}:{start}:{end}_en_de.mp3" filename pattern main.py uses.

What is intentionally NOT ported: main.py's audio_files_prog(), the second
half of mode 5. That function plays audio through the SERVER's speakers and
listens on the SERVER's microphone for "stop"/"resume" voice commands
(speech_recognition + sr.Microphone()) — those are desktop-CLI concepts with
no meaningful web equivalent (a browser can't drive a server's mic/speakers).
The web version's substitute is simpler and arguably better suited to a
browser: it generates the two MP3s and lets the browser's own <audio controls>
player play/pause/scrub them, which is what generate_audio() below returns
URLs for.

Dependency safety: gTTS/pydub (and, transitively, speech_recognition, since
modes_and_logics/speech_output.py imports it at module level even though this
file never calls the mic-based function) are the same packages main.py's mode
5 already requires — nothing new. But if they, or pydub's ffmpeg dependency,
aren't installed, importing them must NOT crash the whole web app and take
modes 1-4 down with it. So that import is wrapped below, and /api/audio/generate
reports the problem as a normal JSON error instead.
"""
import os
import re

from flask import Blueprint, jsonify, request, send_from_directory

from Data.word_list import (
    chapter_one, chapter_two, chapter_three, chapter_four, chapter_five,
    chapter_six, chapter_seven, chapter_eight, chapter_nine, chapter_ten,
    chapter_eleven, chapter_twelve,
)
from modes_and_logics.logics import apply_range_filter, schuflle
from webapp.range_check import check_range  # same helper app.py/review_routes.py use

try:
    from modes_and_logics.speech_output import create_mp3_en_de, create_mp3_de_en
    AUDIO_DEPS_OK, AUDIO_DEPS_ERROR = True, None
except Exception as e:  # gTTS / pydub / speech_recognition / ffmpeg missing
    AUDIO_DEPS_OK, AUDIO_DEPS_ERROR = False, str(e)

audio_bp = Blueprint("audio", __name__, url_prefix="/api/audio")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Same 12-chapter dict as chapters = {1: chapter_one, ...} in main.py — its own
# copy here too (see search_routes.py / review_routes.py for the same choice),
# so this file doesn't reach into either of those for a shared constant.
CHAPTERS_ALL = {
    1: chapter_one, 2: chapter_two, 3: chapter_three, 4: chapter_four,
    5: chapter_five, 6: chapter_six, 7: chapter_seven, 8: chapter_eight,
    9: chapter_nine, 10: chapter_ten, 11: chapter_eleven, 12: chapter_twelve,
}

# Matches exactly the filenames generate_audio() below produces —
# "vocab 3_en_de.mp3" or "vocab 3:5:20_de_en.mp3" — nothing else is servable.
_FILENAME_RE = re.compile(r"^vocab \d+(?::\d+:\d+)?_(?:en_de|de_en)\.mp3$")


@audio_bp.post("/generate")
def generate_audio():
    if not AUDIO_DEPS_OK:
        return jsonify({"error": f"Audio-Erzeugung nicht verfügbar (fehlende Abhängigkeit): {AUDIO_DEPS_ERROR}"}), 503

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

    shuffled = schuflle(chapter_vocab)  # real function, untouched — same shuffle mode 5 uses

    suffix = "" if start is None else f":{start}:{end}"
    name_en_de = f"vocab {chapter}{suffix}_en_de.mp3"
    name_de_en = f"vocab {chapter}{suffix}_de_en.mp3"

    # gTTS is a network call per word, so this can take a while for a long
    # chapter — same blocking wait the CLI has while it builds these files.
    # gTTS's endpoint is known to fail intermittently (rate limits, upstream
    # API changes) and create_mp3_en_de()/create_mp3_de_en() don't catch
    # that themselves, so this route does — a failure here must not take the
    # rest of the app down with it.
    try:
        create_mp3_en_de(shuffled, os.path.join(REPO_ROOT, name_en_de))  # real function, untouched
        create_mp3_de_en(shuffled, os.path.join(REPO_ROOT, name_de_en))  # real function, untouched
    except Exception as e:
        return jsonify({"error": f"Audio-Erzeugung fehlgeschlagen: {e}"}), 502

    return jsonify({
        "chapter": chapter,
        "range": {"start": start, "end": end} if start is not None else None,
        "count": len(shuffled),
        "en_de_url": f"/api/audio/file/{name_en_de}",
        "de_en_url": f"/api/audio/file/{name_de_en}",
    })


@audio_bp.get("/file/<path:filename>")
def audio_file(filename):
    if not _FILENAME_RE.match(filename):
        return jsonify({"error": "Nicht gefunden."}), 404
    return send_from_directory(REPO_ROOT, filename)