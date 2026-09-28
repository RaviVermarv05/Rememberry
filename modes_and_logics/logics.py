from modes_and_logics import verb
from Data import verb_list
import random
import re
from modes_and_logics.Search_Word import *
from modes_and_logics.main_settings import *
from messages import *
sound_wrong=Settings.sound_wrong

def schuflle(data):
    items = list(data.items())
    random.shuffle(items)
    return dict(items)



def search_word(raw_vocab):
    while True:
        search = input("\nenter the word: ").lower().strip()

        if search in ["exit now", "quit now"]:
            return
        found = False
        for i in raw_vocab:
            for j in i:
                if search == j.lower().strip():
                    for k in raw_vocab[i]:
                        found = True
                        print(f"* {k}")
                    print('\n')
            for m in raw_vocab[i]:
                if search == m.lower().strip() or (
                        search == m[4:].lower().strip() and m[0:4].lower() in ['der ', 'die ', 'das ']):
                    for l in i:
                        found = True
                        print(f"* {l} - {m}")
                    print('\n')

        if not found:
            c=input('❌ Word not found, Want to search online Dictionary? ')
            if c.lower().strip() in ['yes','y','ja']:
                Pons_result=Search_in_Pons(search)
                Pons_result.wed()
            else:
                sound_wrong.play()

def apply_range_filter(vocab_dict, start_range, end_range):
    """Filter vocabulary dictionary (or list of dicts) based on range selection"""
    if start_range is None or end_range is None:
        return vocab_dict

    # Adjust indices for 0-based indexing
    start_idx = max(0, start_range - 1)

    if isinstance(vocab_dict, list):
        # vocab_dict is a list of dicts: [{}, {}, ...]
        end_idx = min(len(vocab_dict), end_range)
        return vocab_dict[start_idx:end_idx]

    # Original behavior: vocab_dict is a plain dict
    vocab_items = list(vocab_dict.items())
    end_idx = min(len(vocab_items), end_range)
    filtered_items = vocab_items[start_idx:end_idx]
    return dict(filtered_items)

ARTICLES_WITH_SPACE = ('der ', 'die ', 'das ')

def split_article(ger):
    """Return (article, bare_word) for a German entry, both lower-case.
    article is None when the entry has no leading der/die/das (verbs,
    adjectives, phrases) - there is nothing to strip in that case."""
    g = ger.strip()
    if g[:4].lower() in ARTICLES_WITH_SPACE:
        return g[:3].lower(), g[4:].strip().lower()
    return None, g.lower()

def accepted_english(term):
    """Every spelling accepted for one English term (German -> English mode).
    'desperate(ly)' -> desperate, desperately | 'nurse (m.)' -> nurse |
    'candidate m/w' -> candidate | 'to assist/support' -> to assist, to support |
    'to apply (method)' -> to apply, to apply method. The exact term always works."""
    t = " ".join(str(term).lower().split())
    out = {t}
    t = re.sub(r"\s+m/w(?:/d)?$", "", t)            # "candidate m/w"
    parts = [p.strip() for p in t.split("/")] if "/" in t else [t]
    if len(parts) > 1 and parts[0].startswith("to "):  # "to assist/support"
        parts = [p if p.startswith("to ") else "to " + p for p in parts]
    for p in parts:
        out.add(p)
        m = re.search(r"(\s*)\(([^)]*)\)", p)
        if m:
            inner = m.group(2).strip()
            out.add((p[:m.start()] + p[m.end():]).strip())          # without the bracket
            if not re.fullmatch(r"[mf]\.?", inner):                  # (m.)/(f.) are only labels
                sep = " " if m.group(1) else ""
                out.add((p[:m.start()] + sep + inner + p[m.end():]).strip())
    return out

def accepted_english_set(random_engs):
    accepted = set()
    for e in random_engs:
        accepted |= accepted_english(e)
    return accepted

def selected_range(max_value=None):
    """max_value = number of word pairs available; a start beyond it is
    rejected and an end beyond it is cut back to it."""
    a = input(Range_message.range_selection).lower().strip()
    while True:
        if a in Range_message.selection_yes:
            return None, None  # return None for full range
        elif a in Range_message.selection_no:
            while True:
                try:
                    starting_range = int(input(Range_message.start_range).strip())
                    ending_range = int(input(Range_message.end_range).strip())
                    if starting_range > 0 and ending_range >= starting_range:
                        if max_value is not None:
                            if starting_range > max_value:
                                print(Range_message.out_of_range.format(max=max_value))
                                continue
                            ending_range = min(ending_range, max_value)
                        return starting_range, ending_range
                    else:
                        print(Range_message.invalid_range)
                except ValueError:
                    print(Range_message.valid_range)
        else:
            a = input(Range_message.other).lower().strip()

def review(data, *args):
    """
     ways to call:
      review(chapters, chapter_number, start_range=None, end_range=None)
      review(data, start_range, end_range)
    """
    if len(args) == 2:
        chapter_vocab = data
        start_range, end_range = args
    else:
        chapter_number = args[0]
        start_range = args[1] if len(args) > 1 else None
        end_range = args[2] if len(args) > 2 else None
        chapter_vocab = data[int(chapter_number)]

    s_no = 0
    print("\n")

    if start_range is not None and end_range is not None:
        chapter_vocab = apply_range_filter(chapter_vocab, start_range, end_range)
        print(f"📝 Showing range {start_range}-{end_range}")

    # Detect verb-record format: list of dicts with a 'verb' key
    if isinstance(chapter_vocab, list) and chapter_vocab and "verb" in chapter_vocab[0]:
        for entry in chapter_vocab:
            s_no += 1
            print(f"{s_no}. {entry['verb']} -⟶ {entry['meaning']}")
            print(f"   präsens: {entry['präsens']}  |  präteritum: {entry['präteritum']}  |  perfekt: {entry['perfekt']}")
            if s_no % 10 == 0:
                print("\n")
        return

    # Otherwise fall back to dict / list-of-{key: [german]} handling
    if isinstance(chapter_vocab, list):
        entries = []
        for d in chapter_vocab:
            entries.extend(d.items())
    else:
        entries = chapter_vocab.items()

    for i, german_list in entries:
        s_no += 1
        capitalized_nouns = []

        english = ", ".join(i)
        for word in german_list:
            if word[0:4].lower() in ['der ', 'die ', 'das ']:
                capitalized_nouns.append(word[0:3].lower().strip() + word[3] + word[4].capitalize() + word[5:].lower())
            else:
                capitalized_nouns = german_list

        german = ", ".join(capitalized_nouns)
        print(f"{s_no}. {german} -⟶ {english}")
        if s_no % 10 == 0:
            print("\n")

def handle_verb_mode():
    choice = input("do you wanna review or practice verbs (R/P) ").strip().lower()
    starting_range, ending_range = selected_range()
    ranged_verbs = apply_range_filter(verb_list.verbs, starting_range, ending_range)

    if choice in ("review", "r", "1"):
        review(ranged_verbs, starting_range, ending_range)
    elif choice in ("practice", "p", "2"):
        verb.practice_verbs(ranged_verbs)


def pick_next_word(remaining, completed):
    """Return the next word to quiz on, respecting shuffle settings."""
    candidates = [w for w in remaining if w not in completed]
    if Settings.shuffle_mode:
        return random.choice(candidates)
    return candidates[0]