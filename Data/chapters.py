"""
Chapter registry — which chapters exist, and how they are numbered and grouped.
Managed by the web app's data editor (Einstellungen -> Vokabeln bearbeiten); you can also edit it by hand.

  id      internal number, unique, never shown. Quiz / review / audio use it. Never reuse an id.
  var     name of the dict in Data/word_list.py that holds the chapter's words
  level   group shown in the app: "B1", "B2.1", ...
  number  the chapter's number inside its level (shown as "Kapitel <number>")

A chapter dict that is in word_list.py but missing here is still found (shown under "Weitere").
"""
CHAPTERS = [
    {"id": 1, "var": "chapter_one", "level": "B1", "number": 1},
    {"id": 2, "var": "chapter_two", "level": "B1", "number": 2},
    {"id": 3, "var": "chapter_three", "level": "B1", "number": 3},
    {"id": 4, "var": "chapter_four", "level": "B1", "number": 4},
    {"id": 5, "var": "chapter_five", "level": "B1", "number": 5},
    {"id": 6, "var": "chapter_six", "level": "B1", "number": 6},
    {"id": 7, "var": "chapter_seven", "level": "B1", "number": 7},
    {"id": 8, "var": "chapter_eight", "level": "B1", "number": 8},
    {"id": 9, "var": "chapter_nine", "level": "B1", "number": 9},
    {"id": 10, "var": "chapter_ten", "level": "B1", "number": 10},
    {"id": 11, "var": "chapter_eleven", "level": "B1", "number": 11},
    {"id": 12, "var": "chapter_twelve", "level": "B1", "number": 12},
]