from difflib import SequenceMatcher
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.naive_bayes import MultinomialNB
import joblib
import pandas as pd
import os

ARTICLES = ("der", "die", "das")

class ErrorAnalyzer:
    def __init__(self, model_path="error_model.pkl"):
        self.model_path = model_path
        self.vectorizer = CountVectorizer()
        self.model = None

        if os.path.exists(model_path):
            try:
                self.model, self.vectorizer = joblib.load(model_path)
            except Exception:
                self.model = None

        self.data = pd.DataFrame(columns=["user_answer", "correct_answer", "error_type"])

    @staticmethod
    def _similarity(a, b):
        return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()

    @staticmethod
    def _adaptive_threshold(word, base=0.75):
        """Shorter words need a stricter threshold — a 1-letter typo on a
        4-letter word inflates similarity more than on a long word."""
        length = len(word.strip())
        if length <= 4:
            return max(base, 0.82)
        elif length <= 7:
            return base
        else:
            return base - 0.05

    @staticmethod
    def _strip_article(word):
        """Split off a leading article. Handles article-only input too,
        returning an empty-string core instead of silently misreading
        the article as the noun."""
        word = word.strip()
        parts = word.split(" ", 1)
        if parts[0].lower() in ARTICLES:
            core = parts[1].strip() if len(parts) > 1 else ""
            return parts[0].lower(), core
        return None, word

    def classify_error(self, user_answer, correct_answer):
        user_answer = user_answer.strip()
        correct_answer = correct_answer.strip()

        if user_answer == "":
            return "no_answer"
        if user_answer.lower() == correct_answer.lower():
            return "correct"

        user_article, user_core = self._strip_article(user_answer)
        correct_article, correct_core = self._strip_article(correct_answer)
        threshold = self._adaptive_threshold(correct_core or correct_answer)

        if user_article and user_core == "":
            return "missing_noun"

        if user_article and correct_article:
            if user_article != correct_article:
                if self._similarity(user_core, correct_core) >= threshold:
                    return "wrong_article"
                return "wrong_translation"
            else:
                if self._similarity(user_core, correct_core) >= threshold:
                    return "spelling_error"
                return "wrong_translation"

        if correct_article and not user_article:
            # Only "missing_article" if the noun itself is EXACTLY right —
            # otherwise the noun typo is the real issue, not the article
            if user_core.lower() == correct_core.lower():
                return "missing_article"
            elif self._similarity(user_core, correct_core) >= threshold:
                return "spelling_error"
            return "wrong_translation"

        if self._similarity(user_answer, correct_answer) >= threshold:
            return "spelling_error"
        return "wrong_translation"

    def log_error(self, user_answer, correct_answer):
        etype = self.classify_error(user_answer, correct_answer)
        if etype is None:
            etype = "unclassified"

        new_entry = pd.DataFrame(
            {"user_answer": [user_answer], "correct_answer": [correct_answer], "error_type": [etype]})
        self.data = pd.concat([self.data, new_entry], ignore_index=True)

        if len(self.data) >= 20 and len(self.data) % 5 == 0:
            self.train_model()

    def train_model(self):
        X = self.vectorizer.fit_transform(self.data["user_answer"])
        y = self.data["error_type"]
        model = MultinomialNB()
        model.fit(X, y)
        self.model = model
        joblib.dump((self.model, self.vectorizer), self.model_path)
        print("----- Error model updated with latest mistakes.-----")

    def predict_error(self, user_answer):
        if self.model:
            vec = self.vectorizer.transform([user_answer])
            return self.model.predict(vec)[0]
        return "unknown"

    def closest_term(self, guess, candidates):
        """Pick whichever candidate is closest to the guess, so a wrong
        answer is logged against one clean term instead of a joined string."""
        return max(candidates, key=lambda c: self._similarity(guess, c))