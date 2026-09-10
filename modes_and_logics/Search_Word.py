import requests
import re
from dotenv import load_dotenv
import os

load_dotenv()  # Loads the .env file



class PONSDictionary:
    """PONS German-English Dictionary Client"""

    def __init__(self, api_secret: str):
        self.api_secret = api_secret
        self.headers = {'X-Secret': api_secret}
        self.url = "https://api.pons.com/v1/dictionary"

    def translate(self, word: str, source_lang: str = 'de'):
        """
        Translate between German and English

        Args:
            word: Word or phrase to translate
            source_lang: 'de' for German→English or 'en' for English→German
        """
        params = {
            'q': word,
            'l': 'deen',
            'in': source_lang,
            'ref': 'true',
            'language': 'en'
        }

        try:
            response = requests.get(self.url, headers=self.headers, params=params)

            # Handle different status codes
            if response.status_code == 204:
                print(f"No results found for '{word}'")
                return None
            elif response.status_code == 403:
                print("❌ Authentication failed!")
                print("Possible reasons:")
                print("  - API key not activated yet")
                print("  - Daily limit reached (1000 queries/month)")
                print("  - Contact: c.henn@pons.de")
                return None
            elif response.status_code == 404:
                print("Dictionary not found")
                return None
            elif response.status_code == 503:
                print("Daily API limit reached (1000/month)")
                return None

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            print(f"Error: {e}")
            return None

    def print_results(self, word: str, results: dict, max_results: int = 3):
        """Print simplified and specific translation results"""
        if not results:
            return

        print(f"\n{'=' * 50}")
        print(f"Translation: '{word}'")
        print(f"{'=' * 50}\n")

        found = False

        for lang_result in results:
            hits = lang_result.get('hits', [])
            for hit in hits:
                if hit.get('type') != 'entry':
                    continue  # Ignore examples or idioms

                roms = hit.get('roms', [])
                for rom in roms:
                    headword = self._clean_text(rom.get('headword_full', rom.get('headword', '')))
                    wordclass = rom.get('wordclass', '')
                    arabs = rom.get('arabs', [])

                    for arab in arabs:
                        translations = arab.get('translations', [])
                        for trans in translations[:max_results]:
                            src = self._clean_text(trans.get('source', ''))
                            tgt = self._clean_text(trans.get('target', ''))

                            # Filter out long idiomatic sentences or complex entries
                            if len(src.split()) <= 2 and len(tgt.split()) <= 3:
                                print(f"{src} → {tgt}")
                                found = True

        if not found:
            print("No direct simple translation found.")

    def _print_entry(self, entry: dict, max_results: int):
        """No longer used – now integrated into print_results"""
        pass

    def _clean_text(self, text: str) -> str:
        """Remove HTML tags"""
        return re.sub(r'<.*?>', '', text)


class Search_in_Pons:
    """Online dictionary search wrapper"""

    API_KEY = os.getenv("PONS_API_KEY")

    def __init__(self, search):
        self.search = search.strip()
        self.pons = PONSDictionary(self.API_KEY)

    def detect_language(self, text):
        """Rudimentary detection for German vs English words"""
        # Simple German pattern check (capitalized nouns, umlauts, ß, etc.)
        german_chars = "äöüß"
        if any(c in text.lower() for c in german_chars):
            return "de"
        elif re.match(r"^[A-ZÄÖÜ][a-zäöüß]+$", text):  # e.g. Haus, Baum
            return "de"
        else:
            # Could be either (like 'fast')
            return "ambiguous"

    def wed(self):
        """Smart search with language detection"""
        print("\n--- Online Dictionary Search ---")

        lang_detected = self.detect_language(self.search)

        if lang_detected == "de":
            source_lang = "de"
        elif lang_detected == "ambiguous":
            # Ask user to choose the meaning
            print(f"The word '{self.search}' exists in both English and German.")
            choice = input("Translate from (1) German→English or (2) English→German? ").strip()
            source_lang = "de" if choice == "1" else "en"
        else:
            source_lang = "en"

        results = self.pons.translate(self.search, source_lang=source_lang)
        if results:
            self.pons.print_results(self.search, results)
        else:
            print("No result found.")



