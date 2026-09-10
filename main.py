from modes_and_logics import logics
from Data.word_list import *
from modes_and_logics.speech_output import audio_files_prog
from modes_and_logics.logics import *
from modes_and_logics.description_ai import run_context_mode
from modes_and_logics.error_classifier import ErrorAnalyzer
from sound.load_sound import *
trials=Settings.trials



def result_in_german(rate):
    German_feedback1=German_feedback(rate,correct_answers,total_attempts)
    print(German_feedback.congrats_msg)
    print(German_feedback1.Erfolgsquote())

    if int(rate) != 100 and len(practice_words) != 0:
        print(German_feedback.practice_head)

        for i in practice_words:
            if i == ' ':
                print(i)
            else:
                print(f"* {i}")

    elif int(rate) == 100:
        print(German_feedback.all_complete)

def result_in_eng(rate):
    Eng_feedback1=Eng_feedback(rate,correct_answers,total_attempts)
    print(Eng_feedback.congrats_msg)
    print(Eng_feedback1.success_rate())

    if int(rate) != 100 and len(practice_words) != 0:
        print(Eng_feedback.practice_head)

        for i in practice_words:
            if i == ' ':
                print(i)
            else:
                print(f"* {i}")

    elif int(rate) == 100:
        print(Eng_feedback.all_complete)

def total_german_words():
    v = 0
    for i in raw_vocab:
        for _ in raw_vocab[i]:
            v += 1
    Total_german_words1=Total_german_words(v)
    print(Total_german_words1.total_msg())

def quiz_ger_eng(german_words, random_engs, wrong_guesses, display_eng):
    global total_attempts, correct_answers
    remaining_germans = ", ".join(german_words)
    for _ in range(trials):
        answer = input(f"{remaining_germans} - ").lower().strip()
        total_attempts += 1

        if answer == "":
            error_analyzer.log_error(answer, error_analyzer.closest_term(answer, random_engs))
            print(Quiz_ger_eng.wrong_ans)
            sound_wrong.play()
            wrong_guesses += 1
            continue

        if answer in [e.lower().strip() for e in random_engs]:
            sound_correct.play()
            print(Quiz_ger_eng.right_ans)
            correct_answers += 1
            break
        else:
            print(Quiz_ger_eng.wrong_ans)
            sound_wrong.play()

            closest = error_analyzer.closest_term(answer, random_engs)
            error_analyzer.log_error(answer, closest)

            Quiz_ger_eng1 = Quiz_ger_eng(wrong_guesses)
            print(Quiz_ger_eng1.incorrect_attempts())
            wrong_guesses += 1
    else:
        print(Quiz_ger_eng.incorrect_head)
        sound_wrong.play()
        print(Quiz_ger_eng.correct_head)
        print(f"- {display_eng}")
        for g in german_words:
            practice_words.append(g)
        practice_words.append(' ')


def quiz_eng_ger(guessed, german_words, display_eng, wrong_guesses):
    global total_attempts, correct_answers
    while len(guessed) < len(german_words):
        answer = input(f"{display_eng} - ").lower().strip()
        total_attempts += 1
        matched = False

        # Log blank answers explicitly instead of skipping them
        if answer == "":
            closest = error_analyzer.closest_term(answer, german_words)
            error_analyzer.log_error(answer, closest)
            wrong_guesses += 1
            print(Quiz_eng_ger.wrong_ans)
            sound_wrong.play()
            print(f"Falsche Versuche: {wrong_guesses}/{Settings.trials}")
            if wrong_guesses >= trials:
                print(Quiz_eng_ger.incorrect_head)
                sound_wrong.play()
                print(Quiz_eng_ger.correct_head)
                for g in german_words:
                    print(f"- {g}")
                    practice_words.append(g)
                practice_words.append(' ')
                break
            continue

        for ger in german_words:
            if ger in guessed:
                continue

            correct_word = ger[4:].lower().strip()
            correct_article = ger[0:3].lower()

            if answer == ger.lower().strip() or answer == correct_word:
                print(Quiz_eng_ger.right_ans)
                sound_correct.play()
                matched = True

                if Settings.show_article:
                    if answer == correct_word:
                        raw_article_input = input(Quiz_eng_ger.enter_right_article).lower().strip()
                        # Only take the first token — user may retype the noun too
                        article = raw_article_input.split(" ")[0] if raw_article_input else ""
                        Quiz_eng_ger1 = Quiz_eng_ger(ger)

                        if article == correct_article:
                            print(Quiz_eng_ger1.artikel_ist_richtig())
                            sound_correct.play()
                            correct_answers += 1
                        else:
                            print(Quiz_eng_ger1.artikel_ist_falsch())
                            sound_wrong.play()
                            # log just the parsed article token, not the raw multi-word input
                            error_analyzer.log_error(f"{article} {correct_word}", ger)
                        # NOTE: total_attempts intentionally NOT incremented again here —
                        # the article check is part of the same vocabulary attempt
                    else:
                        correct_answers += 1
                else:
                    correct_answers += 1

                guessed.add(ger)
                break

        if not matched:
            wrong_guesses += 1
            print(Quiz_eng_ger.wrong_ans)
            sound_wrong.play()

            # Log against the closest single German term, not the joined string (fixes #1)
            closest = error_analyzer.closest_term(answer, german_words)
            error_analyzer.log_error(answer, closest)

            print(f"Falsche Versuche: {wrong_guesses}/{Settings.trials}")

            if wrong_guesses >= trials:
                print(Quiz_eng_ger.incorrect_head)
                sound_wrong.play()
                print(Quiz_eng_ger.correct_head)
                for g in german_words:
                    print(f"- {g}")
                    practice_words.append(g)
                practice_words.append(' ')
                break

    return wrong_guesses


print('''Welcome to German Vocabulary!
Choose Mode:
1 - English to German
2 - German to English
3 - search
4 - review
5 - audio
6 - context mode
7 - verbs
''')

correct_answers = 0
total_attempts = 0
practice_words = []
error_analyzer = ErrorAnalyzer()

chapters = {
    1: chapter_one,
    2: chapter_two,
    # 3: chapter_three,
    # 4: chapter_four,
    # 5: chapter_five,
    # 6: chapter_six,
    # 7: chapter_seven,
    8: chapter_eight,
    9: chapter_nine,
    10: chapter_ten,
    11: chapter_eleven,
    12: chapter_twelve
}

# Ask the user for quiz mode
while True:
    mode_input = input("Enter your choice: ").strip()

    if mode_input in ("1", "2", "3", "4", "5","6","7"):
        mode = int(mode_input)
        break
    elif mode_input.lower().strip() in ["show", "review"]:
        mode = 4
        break
    else:
        print("Invalid input. Try again!")
        sound_wrong.play()

# Initialize range variables
start_range, end_range = None, None

if mode in [1, 2, 4, 5, 6]:
    # Ask user for chapter no
    while True:
        chapter_number = input("Enter chapter number 1-12 ").strip()
        if chapter_number in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"):
            raw_vocab = int(chapter_number)
            break
        else:
            print("Invalid input. Please enter valid chapter.")
            sound_wrong.play()

    # Get range selection
    start_range, end_range = selected_range()

    # Get chapter vocabulary and apply range filter
    raw_vocab = chapters.get(raw_vocab)
    if start_range is not None and end_range is not None:
        raw_vocab = apply_range_filter(raw_vocab, start_range, end_range)
        print(f"📚 Working on range {start_range}-{end_range} ({len(raw_vocab)} word pairs)")
    else:
        print(f"📚 Working on all words ({len(raw_vocab)} word pairs)")

else:
    raw_vocab = chapter_eleven | chapter_twelve | chapter_ten | chapter_nine | chapter_eight | chapter_one | chapter_two
    total_german_words()

# Flatten to list of ((eng_terms), german_word) pairs
vocab_pairs = []
for eng_terms, ger_list in raw_vocab.items():
    for ger in ger_list:
        vocab_pairs.append((eng_terms, ger))

# Get all unique English term tuples
remaining = []
for eng, _ in vocab_pairs:
    if eng not in remaining:  # keep order, avoid duplicates
        remaining.append(eng)
completed = set()


def run_vocab_round(random_engs, display_eng):
    """Handle a single English<->German quiz round for the given word."""
    german_words = [ger for eng, ger in vocab_pairs if eng == random_engs]

    if mode == 2:  # German → English
        print("\n📘 Enter the appropriate English word")
        quiz_ger_eng(german_words, random_engs, wrong_guesses=0, display_eng=display_eng)
    elif mode == 1:  # English → German
        word_label = "deutsches Wort" if len(german_words) == 1 else "deutsche Wörter"
        print(f"\n📘 Es gibt {len(german_words)} {word_label}.")
        quiz_eng_ger(guessed=set(), german_words=german_words,
                     display_eng=display_eng, wrong_guesses=0)

    completed.add(random_engs)

def logic():
    global correct_answers, total_attempts, practice_words

    # Modes 1 & 2 are the word-guessing quiz; everything else dispatches elsewhere
    if mode in (1, 2):
        if len(completed) == len(remaining):
            rate = round((correct_answers / total_attempts) * 100, 2) if total_attempts else 0
            if mode == 2:
                result_in_eng(rate)
            else:
                result_in_german(rate)
            return False

        random_engs = pick_next_word(remaining, completed)
        display_eng = " / ".join(random_engs)
        run_vocab_round(random_engs, display_eng)
        return True

    elif mode == 3:
        search_word(raw_vocab)
    elif mode == 4:
        review(chapters, chapter_number, start_range, end_range)
    elif mode == 5:
        audio_files_prog(logics.schuflle(raw_vocab))
    elif mode == 6:
        run_context_mode(logics.schuflle(raw_vocab))
        return False
    elif mode == 7:
        handle_verb_mode()

# Run the game loop
game_is_on = True
while game_is_on:
    game_is_on = logic()

if not game_is_on:
    if len(error_analyzer.data) > 0:
        print("\n🧩 Error Pattern Summary:")
        grouped = error_analyzer.data.groupby("error_type")
        for err, group in sorted(grouped, key=lambda x: len(x[1]), reverse=True):
            print(f"\n  {err} ({len(group)} times):")
            for word, n in group["correct_answer"].value_counts().items():
                print(f"    • {word}  ({n}x)")

