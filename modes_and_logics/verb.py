import random
from sound.load_sound import *
from messages import Quiz_ger_eng


def practice_verbs(verbs):
    FIELDS = [
        "meaning",
        "verb",
        "präsens",
        "präteritum",
        "perfekt"
    ]


    def normalize_answer(answer):
        return answer.strip().lower()


    def get_label(field):

        labels = {
            "meaning": "Meaning",
            "verb": "Verb",
            "präsens": "Präsens (er/sie/es)",
            "präteritum": "Präteritum",
            "perfekt": "Perfekt"
        }

        return labels[field]


    def practice_verb(verb_data, verb_number, total_verbs):

        print("\n" + "=" * 60)
        print(f"VERB {verb_number}/{total_verbs}")
        print("=" * 60)

        # ----------------------------------------
        # Pick ONE random value as the clue
        # ----------------------------------------

        clue_field = random.choice(FIELDS)

        clue_value = verb_data[clue_field]

        print(f"\nCLUE:  {clue_value}")

        print("\nComplete the remaining fields:")

        # ----------------------------------------
        # Ask for the other 4 values
        # ----------------------------------------

        answer_fields = [
            field for field in FIELDS
            if field != clue_field
        ]

        # Randomize the order of the 4 questions
        random.shuffle(answer_fields)

        correct = 0
        wrong = 0
        mistakes = []

        for field in answer_fields:

            label = get_label(field)

            user_answer = input(f"\n{label}: ")

            # Quit
            if user_answer.strip().lower() == "q":
                return None

            user_answer = normalize_answer(user_answer)

            correct_answer = normalize_answer(
                str(verb_data[field])
            )

            if user_answer == correct_answer:

                print(Quiz_ger_eng.right_ans)
                sound_correct.play()

                correct += 1

            else:

                print(Quiz_ger_eng.wrong_ans)
                sound_wrong.play()

                print(f"⚠️ Correct answer: {verb_data[field]}")

                wrong += 1

                mistakes.append({
                    "verb": verb_data["verb"],
                    "clue": clue_value,
                    "question": label,
                    "your_answer": user_answer,
                    "correct_answer": verb_data[field]
                })

        print("\n✓ Verb completed!")

        return correct, wrong, mistakes


    def show_final_result(
        total_correct,
        total_wrong,
        mistakes,
        total_questions
    ):

        print("\n")
        print("=" * 60)
        print("SESSION COMPLETE")
        print("=" * 60)

        print(f"\nCorrect: {total_correct}")
        print(f"Wrong:   {total_wrong}")

        accuracy = (
            total_correct / total_questions
        ) * 100

        print(f"Accuracy: {accuracy:.1f}%")

        # ----------------------------------------
        # Mistakes
        # ----------------------------------------

        if mistakes:

            print("\n" + "=" * 60)
            print("YOUR MISTAKES")
            print("=" * 60)

            for number, mistake in enumerate(
                mistakes,
                start=1
            ):

                print(f"\n{number}. Verb: {mistake['verb']}")
                print(f"Clue: {mistake['clue']}")
                print(f"Question: {mistake['question']}")
                print(f"Your answer: {mistake['your_answer']}")
                print(
                    f"Correct answer: "
                    f"{mistake['correct_answer']}"
                )

        else:

            print("\n🎉 Perfect! No mistakes!")


    def main():

        print("=" * 60)
        print("             GERMAN VERB PRACTICE")
        print("=" * 60)

        print("\nRules:")
        print("- Each verb appears only once.")
        print("- One random value is shown as the clue.")
        print("- You provide the other four values.")
        print("- After completing a verb, it will never appear again.")
        print("- Type 'q' at any time to quit.")

        input("\nPress ENTER to start...")

        # ----------------------------------------
        # Create a copy and shuffle the verbs
        # ----------------------------------------

        practice_verbs = verbs.copy()
        random.shuffle(practice_verbs)

        total_verbs = len(practice_verbs)

        total_correct = 0
        total_wrong = 0
        all_mistakes = []

        # Each verb produces exactly 4 questions
        total_questions = total_verbs * 4

        # ----------------------------------------
        # Practice each verb exactly once
        # ----------------------------------------

        for verb_number, verb_data in enumerate(
            practice_verbs,
            start=1
        ):

            result = practice_verb(
                verb_data,
                verb_number,
                total_verbs
            )

            # User quit
            if result is None:

                print("\nPractice session ended.")
                return

            correct, wrong, mistakes = result

            total_correct += correct
            total_wrong += wrong

            all_mistakes.extend(mistakes)

        # ----------------------------------------
        # Final result
        # ----------------------------------------

        show_final_result(
            total_correct,
            total_wrong,
            all_mistakes,
            total_questions
        )


    main()