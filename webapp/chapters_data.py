"""
Single source of truth for "all twelve chapters as a {number: dict} lookup",
used by mode 3 (search_routes.py), mode 4 (review_routes.py) and mode 5
(audio_routes.py). Those three files used to each define their own identical
copy of this dict, which meant adding or changing a chapter in
Data/word_list.py required editing four files instead of one. Now it's just
these two:

  1. Data/word_list.py   — add the new chapter dict, e.g. chapter_thirteen = {...}
  2. webapp/chapters_data.py (this file) — add it to CHAPTERS_ALL below

search_routes.py, review_routes.py and audio_routes.py then all pick it up
automatically — nothing in them needs to change.

This is intentionally separate from the CHAPTERS dict in app.py, which is a
deliberate SUBSET (modes 1/2 only use chapters 1, 2, 8-12 — chapters 3-7 have
very little data, see Data/word_list.py) used by the quiz modes. Whether a
newly added chapter should also appear in modes 1/2's quiz is a separate,
deliberate choice — so adding a line here does not change that subset; it
stays exactly as app.py already defines it.
"""
from Data.word_list import (
    chapter_one, chapter_two, chapter_three, chapter_four, chapter_five,
    chapter_six, chapter_seven, chapter_eight, chapter_nine, chapter_ten,
    chapter_eleven, chapter_twelve,
)

CHAPTERS_ALL = {
    1: chapter_one, 2: chapter_two, 3: chapter_three, 4: chapter_four,
    5: chapter_five, 6: chapter_six, 7: chapter_seven, 8: chapter_eight,
    9: chapter_nine, 10: chapter_ten, 11: chapter_eleven, 12: chapter_twelve,
}