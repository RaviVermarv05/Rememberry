import traceback
import os
from dotenv import load_dotenv
from sound.load_sound import *
from groq import Groq

# ✅ Load your .env file
load_dotenv(override=True)


def get_difficulty(word):
    classify_prompt = (
        f"Classify the German word '{word}' for a vocabulary learner. "
        f"Answer with exactly one word: 'concrete' or 'abstract'.\n\n"
        f"'concrete' = a word that can usually be understood through a "
        f"physical object, observable action, person, place, or clearly "
        f"imagined everyday situation.\n"
        f"'abstract' = a concept, relationship, connector, grammatical "
        f"function, modal particle, or word whose meaning is difficult "
        f"to represent through a specific observable situation.\n\n"
        f"Examples:\n"
        f"concrete: Regenschirm, Batterie, schauen, ausgehen, austauschen\n"
        f"abstract: trotzdem, deshalb, Zusammenhang, allerdings, seitdem\n\n"
        f"Word: '{word}'"
    )
    try:
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        result = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[{"role": "user", "content": classify_prompt}]
        )
        answer = result.choices[0].message.content.strip().lower()
        return "abstract" if "abstract" in answer else "concrete"
    except Exception as e:
        print(f"⚠️ Difficulty classification failed for '{word}': {e}")
        return "concrete"  # safe fallback


def get_hint(word):
    difficulty = get_difficulty(word)
    if difficulty == "abstract":
        # direct, simple gloss — don't force a scene that doesn't exist
        prompt = (
            f"Create a short, easy-to-understand context clue for the German word '{word}' "
            f"for an English-speaking vocabulary learner.\n\n"

            f"RULES:\n"
            f"1. Never translate, define, or directly reveal the word's meaning.\n"
            f"2. Never write the German word '{word}' in the response. Use '___' instead if needed.\n"
            f"3. Show WHEN and HOW a German speaker naturally uses the word, rather than giving "
            f"a dictionary-style definition.\n"
            f"4. For connectors, conjunctions, and prepositions, show the relationship between "
            f"ideas through a simple situation or example sentence.\n"
            f"5. Make the clue specific enough to recognize the target, but do not invent a "
            f"false distinction from similar words.\n"
            f"6. Use simple A2-B1 English and the target's most common everyday use.\n"
            f"7. Write 10-18 words. An example sentence with '___' is allowed when useful.\n\n"
            f"8. Use natural language and natural example sentences. Never invent an "
            f"unnatural collocation or sentence merely to make the target word seem unique.\n"

            f"9. If the target has a close synonym or near-equivalent word, do not "
            f"force an artificial distinction. Give the most natural context for the "
            f"target word instead.\n"
            f"10. If you provide an example sentence, make sure the target word fits "
            f"that sentence exactly as a native speaker would naturally use it."

            f"Example:\n"
            f"Word: 'seitdem' → "
            f"'Connects a past event with something that has continued until now: \"___ ich umgezogen bin, wohne ich hier.\"'\n\n"

            f"Now write one clue for '{word}'. "
            f"Return only the clue, with no labels or quotation marks."
        )
    else:
        prompt = (
            f"Create a short, easy-to-guess context clue for the German word '{word}' "
            f"for an English-speaking vocabulary learner.\n\n"

            f"RULES:\n"
            f"1. Never translate, define, or directly reveal the word's meaning.\n"
            f"2. Never write the German word '{word}' in the response. Use '___' instead if needed.\n"
            f"3. Describe the TARGET itself, not a related object, tool, result, or consequence.\n"
            f"4. Use the word's most common everyday meaning and give a concrete, realistic situation "
            f"with 2-3 distinctive details that make the answer easy to guess.\n"
            f"5. If similar words could be confused with the target, include a detail that helps "
            f"distinguish the target without mentioning the other words.\n"
            f"6. Use simple A2-B1 English and avoid vague descriptions.\n"
            f"7. Write 12-20 words in one natural sentence.\n\n"
            f"8. Use natural language and natural example sentences. Never invent an "
            f"unnatural collocation or sentence merely to make the target word seem unique.\n"

            f"9. If the target has a close synonym or near-equivalent word, do not "
            f"force an artificial distinction. Give the most natural context for the "
            f"target word instead.\n"

            f"Example:\n"
            f"Word: 'Regenschirm' → "
            f"'You carry this on rainy days and open it above your head before walking outside.'\n\n"

            f"Now write one clue for '{word}'. "
            f"Return only the clue, with no labels or quotation marks."
        )

    try:
        api_key = os.getenv("GROQ_API_KEY")
        # print("API key loaded:", bool(api_key))
        # print("API key prefix:", api_key[:10] if api_key else None)
        if not api_key:
            raise ValueError("GROQ_API_KEY not found. Check your .env file.")

        # ✅ Initialize the client
        client = Groq(api_key=api_key)
        # models = client.models.list()
        #
        # print("\nAvailable models:")
        # for model in models.data:
        #     print(model.id)

        chat_completion = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": "You are a helpful assistant for German learners."},
                {"role": "user", "content": prompt}
            ]
        )

        # ✅ Return the AI-generated description
        return chat_completion.choices[0].message.content

    except Exception as e:
        print(f"⚠️ AI description error for '{word}': {e}")
        traceback.print_exc()
        return f"No AI description available for '{word}'."


def run_context_mode(raw_vocab):
    """
    Mode 6: Context-based quiz using AI descriptions.
    Shows an AI-generated English hint and asks the user for the German word.
    """
    correct = 0
    total = 0

    for eng_terms, ger_list in raw_vocab.items():
        for ger_word in ger_list:
            desc = get_hint(ger_word)
            if not desc:
                continue  # Skip if AI failed

            print(f"\n📘 Description: {desc}")
            answer = input("Your answer (in German): ").strip().lower()
            total += 1

            if answer == ger_word.lower().strip() or answer == ger_word[4:].lower().strip():
                sound_correct.play()
                print("✅ Correct!")
                correct += 1
            else:
                sound_wrong.play()
                print(f"❌ Wrong! The correct answer was: {ger_word}")

    if total > 0:
        score = round((correct / total) * 100, 2)
        print(f"\n🎯 Your accuracy: {score}% ({correct}/{total})")
    else:
        print("⚠️ No words processed.")
