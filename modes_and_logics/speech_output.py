from gtts import gTTS
import os
import time
import platform
import threading
import speech_recognition as sr


pause_signal = False

def audio_files_prog(data):
    global pause_signal
    pause_signal = False
    stop_thread = False

    # Function to safely generate and save TTS audio
    def safe_tts_save(text, lang, filename, slow=False, retries=3):
        for attempt in range(retries):
            try:
                if not text.strip():
                    print("Skipping empty text.")
                    return
                tts = gTTS(text=text, lang=lang, slow=slow)
                tts.save(filename)
                return
            except Exception as e:
                print(f"TTS error on attempt {attempt + 1}: {e}")
                time.sleep(1)
        raise RuntimeError("Failed to generate TTS after multiple attempts.")

    # Function to play audio file based on OS
    def play_audio(filename):
        try:
            system = platform.system()
            if system == 'Windows':
                os.system(f"start {filename}")
            elif system == 'Darwin':  # macOS
                os.system(f"afplay {filename}")
            elif system == 'Linux':
                os.system(f"mpg123 {filename}")  # Assumes mpg123 is installed
            else:
                raise OSError("Unsupported OS for audio playback")
        except Exception as e:
            print(f"Audio playback failed: {e}")

    # Background thread for speech command recognition
    def listen_for_commands():
        nonlocal stop_thread
        global pause_signal
        recognizer = sr.Recognizer()
        mic = sr.Microphone()
        with mic as source:
            recognizer.adjust_for_ambient_noise(source)
        while not stop_thread:
            with mic as source:
                try:
                    audio = recognizer.listen(source, timeout=5, phrase_time_limit=3)
                    command = recognizer.recognize_google(audio).lower()
                    print(f"You said: {command}")
                    if "stop" in command:
                        print("Pausing playback.")
                        pause_signal = True
                    elif "resume" in command:
                        print("Resuming playback.")
                        pause_signal = False
                except sr.UnknownValueError:
                    continue
                except sr.WaitTimeoutError:
                    continue
                except Exception as e:
                    print(f"Listening error: {e}")
                    continue

    def wait_if_paused():
        while pause_signal:
            print("⏸ Paused... Say 'resume' to continue.")
            time.sleep(1)

    # Start listener thread
    listener_thread = threading.Thread(target=listen_for_commands)
    listener_thread.daemon = True
    listener_thread.start()

    # Main audio playback loop
    try:
        for key, german_words in data.items():
            wait_if_paused()

            english_words = ", ".join(key)
            print("\n")
            print(f"English: {english_words}")
            safe_tts_save(english_words, 'en', "temp.mp3")
            play_audio("temp.mp3")
            time.sleep(1)  # Avoid rapid-fire requests

            for word in german_words:
                wait_if_paused()
                print(f"German: {word}")
                safe_tts_save(word, 'de', "temp.mp3", slow=True)
                play_audio("temp.mp3")
                time.sleep(2)
    finally:
        stop_thread = True
        try:
            os.remove("temp.mp3")
        except Exception as e:
            print(f"Could not delete temp.mp3: {e}")
