"""
Speaker button in "Wörter durchsehen" -> real German pronunciation. A self-contained Blueprint,
same pattern as explain_routes.py / search_routes.py. Nothing existing is modified.

  GET /api/speak?text=beweisen        -> audio/mpeg (one German word or short phrase)

Uses gTTS with lang="de" — the same engine the audio mode (speech_output.py) already uses, so
the pronunciation matches your vocabulary MP3s. It needs an internet connection (gTTS asks
Google's speech service). Every word is generated once and kept in the system temp folder
(not in the project, so git and the live-reload never see it); the second click is instant.
If gTTS is not installed the endpoint answers 503 and the page falls back to the browser voice.
"""
import hashlib
import os
import re
import tempfile
import threading

from flask import Blueprint, jsonify, request, send_file

try:
    from gtts import gTTS
except Exception:            # gTTS missing -> only this endpoint is unavailable
    gTTS = None

speak_bp = Blueprint("speak", __name__, url_prefix="/api/speak")

SLOW = False                 # True = slower, more drawn-out speech (what the MP3 audio mode uses)
MAX_LEN = 80
_ALLOWED = re.compile(r"^[\w\s.,;:!?()'’/\-äöüÄÖÜß]+$")
CACHE_DIR = os.path.join(tempfile.gettempdir(), "rememberry_speak")
_lock = threading.Lock()


@speak_bp.route("", methods=["GET"])
def speak():
    text = (request.args.get("text") or "").strip()
    if not text or len(text) > MAX_LEN or not _ALLOWED.match(text):
        return jsonify({"error": "Ungültiger Text."}), 400
    if gTTS is None:
        return jsonify({"error": "gTTS ist nicht installiert (pip install gTTS)."}), 503

    key = hashlib.sha1(f"de|{int(SLOW)}|{text}".encode("utf-8")).hexdigest()
    path = os.path.join(CACHE_DIR, key + ".mp3")
    with _lock:
        if not os.path.exists(path):
            try:
                os.makedirs(CACHE_DIR, exist_ok=True)
                tmp = path + ".part"
                gTTS(text=text, lang="de", slow=SLOW).save(tmp)
                os.replace(tmp, path)
            except Exception as e:   # no internet / Google refused
                return jsonify({"error": f"Sprachausgabe nicht erreichbar: {e}"}), 502
    return send_file(path, mimetype="audio/mpeg", max_age=86400)