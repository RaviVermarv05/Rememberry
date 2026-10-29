"""
Chapter registry logic — the one place that decides "which chapters exist and what are
they called". Pure Python, no Flask, no imports from the rest of the app, so it is used by
the web app (chapters_data.py), the terminal version (main.py) and the data editor
(data_routes.py) alike, and none of them can disagree.

Inputs
  * Data/chapters.py     optional registry: a list of {"id", "var", "level", "number"}
  * Data/word_list.py    the chapter dicts themselves (chapter_one = {...}, chapter_13 = {...})

Rules (they are what keeps the app from ever crashing on chapter changes)
  * `id`      internal, unique, never shown. Quiz / review / audio / search all use it.
              Chapters 1-12 keep ids 1-12, so nothing that already worked changes.
  * `var`     name of the dict in Data/word_list.py. A registry entry whose variable no
              longer exists is skipped (not an error).
  * `level`   "B1", "B2.1", ... — lets "B2.1 Kapitel 1" and "B1 Kapitel 1" coexist.
  * `number`  the chapter's number inside its level (what is shown as "Kapitel N").
  * A chapter dict that is in word_list.py but not in the registry is still picked up
    (level "Weitere") — adding a chapter by hand in word_list.py just works.
  * No registry / broken registry -> legacy behaviour: chapter_one..chapter_twelve = 1..12 (B1).
  * Duplicate ids / variables / unusable entries are skipped, never raised.
"""
import ast

LEGACY_VARS = {
    "chapter_one": 1, "chapter_two": 2, "chapter_three": 3, "chapter_four": 4,
    "chapter_five": 5, "chapter_six": 6, "chapter_seven": 7, "chapter_eight": 8,
    "chapter_nine": 9, "chapter_ten": 10, "chapter_eleven": 11, "chapter_twelve": 12,
}
LEGACY_LEVEL = "B1"
EXTRA_LEVEL = "Weitere"
CHAPTER_PREFIX = "chapter"


def chapter_vars_from_source(text):
    """Names (in file order) of top-level `chapter... = {literal dict}` assignments of word_list.py."""
    names = []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return names
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and isinstance(node.value, ast.Dict)
                and node.targets[0].id.startswith(CHAPTER_PREFIX)
                and node.targets[0].id not in names):
            names.append(node.targets[0].id)
    return names


def _clean_entry(e):
    if not isinstance(e, dict):
        return None
    i, var, level, number = e.get("id"), e.get("var"), e.get("level"), e.get("number")
    if (not isinstance(i, int) or isinstance(i, bool) or i < 1 or not isinstance(var, str) or not var
            or not isinstance(level, str) or not level.strip()
            or not isinstance(number, int) or isinstance(number, bool) or number < 1):
        return None
    return {"id": i, "var": var, "level": level.strip(), "number": number}


def resolve(registry, available_vars):
    """-> list of {"id","var","level","number","short","label","registered"} in display order
    (levels in order of first appearance, chapters by number inside each level)."""
    available = list(available_vars)
    infos, used_ids, used_vars = [], set(), set()

    entries = registry if isinstance(registry, list) and registry else None
    if entries is None:   # legacy: the twelve original chapters
        entries = [{"id": n, "var": v, "level": LEGACY_LEVEL, "number": n}
                   for v, n in LEGACY_VARS.items() if v in available]
        registered = False
    else:
        registered = True

    for raw in entries:
        e = _clean_entry(raw)
        if e is None or e["var"] not in available or e["id"] in used_ids or e["var"] in used_vars:
            continue
        used_ids.add(e["id"]); used_vars.add(e["var"])
        infos.append({**e, "registered": registered})

    next_id = max(used_ids, default=0)
    extra_no = 0
    for v in available:
        if v in used_vars:
            continue
        next_id += 1; extra_no += 1
        used_vars.add(v)
        infos.append({"id": next_id, "var": v, "level": EXTRA_LEVEL, "number": extra_no, "registered": False})

    level_order = []
    for i in infos:
        if i["level"] not in level_order:
            level_order.append(i["level"])
    infos.sort(key=lambda i: (level_order.index(i["level"]), i["number"], i["id"]))

    multi = len(level_order) > 1
    for i in infos:
        i["short"] = f"Kapitel {i['number']}"
        i["label"] = f"{i['level']} · {i['short']}" if multi else i["short"]
    return infos