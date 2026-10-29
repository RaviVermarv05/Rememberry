"""
Single source of truth for "which chapters exist" as {id: dict}, used by every mode
(quiz, search, review, audio, context, explain) and by the data editor.

Nothing here is hard-coded any more. The chapters come from
  * Data/chapters.py    the registry (id / level / number per chapter), and
  * Data/word_list.py   the chapter dicts themselves,
combined by webapp/chapter_registry.py. So to add, remove or rename a chapter you no longer
edit this file — use the data editor (Einstellungen -> Vokabeln bearbeiten), or add a
`chapter_xyz = {...}` dict to word_list.py by hand: it is found automatically.

If the registry is missing or broken, the twelve original chapters are used exactly as before.

Exports
  CHAPTER_INFOS  ordered list of {id, var, level, number, short, label}
  CHAPTER_META   {id: info}
  CHAPTERS_ALL   {id: the chapter's {english tuple: [german, ...]} dict}   (same name as before)

Note: app.py's CHAPTERS is this same dict, so quiz modes 1/2 see every chapter too.
"""
import os

import Data.word_list as _word_list
from webapp.chapter_registry import chapter_vars_from_source, resolve

try:
    from Data.chapters import CHAPTERS as _REGISTRY
except Exception as _e:                      # missing file, syntax error, wrong shape ...
    _REGISTRY = None
    if not isinstance(_e, ImportError):
        print(f"[chapters] Data/chapters.py could not be read ({_e}); using the default 12 chapters.")

with open(_word_list.__file__, "rb") as _f:
    _available = [n for n in chapter_vars_from_source(_f.read().decode("utf-8"))
                  if isinstance(getattr(_word_list, n, None), dict)]

CHAPTER_INFOS = resolve(_REGISTRY, _available)
CHAPTER_META = {i["id"]: i for i in CHAPTER_INFOS}
CHAPTERS_ALL = {i["id"]: getattr(_word_list, i["var"]) for i in CHAPTER_INFOS}