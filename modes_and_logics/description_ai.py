import traceback
import os
from dotenv import load_dotenv
from sound.load_sound import *
from groq import Groq

# ✅ Load your .env file
load_dotenv(override=True)

def get_ai_description(word):
    """Generate a short English description for a given German word."""
    prompt = (
        f"Describe the German word '{word}' using simple English in 20 words or fewer. "
        f"Do NOT translate, define, or hint at its English meaning directly. "
        f"Instead, describe what the word represents, when or how it is used, "
        f"so that the learner can infer its meaning from context. "
        f"Respond only with the description, no examples or quotes."
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


# def get_ai_description(word):
#     prompt=f'Currently no AI description is available for the word: {word}'
#     return prompt

def run_context_mode(raw_vocab):
    """
    Mode 6: Context-based quiz using AI descriptions.
    Shows an AI-generated English hint and asks the user for the German word.
    """
    correct = 0
    total = 0

    for eng_terms, ger_list in raw_vocab.items():
        for ger_word in ger_list:
            desc = get_ai_description(ger_word)
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
