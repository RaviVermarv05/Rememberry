import os
import pygame

SOUND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sound")


class _NoSound:
    """Silent stand-in used when no audio device is available (e.g. web server)."""
    def play(self, *a, **k): pass
    def set_volume(self, *a, **k): pass


def _load_sound(filename):
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        return pygame.mixer.Sound(os.path.join(SOUND_DIR, filename))
    except (pygame.error, FileNotFoundError):
        return _NoSound()


class Settings:

    # Quiz Settings
    trials = 2  # 1 being the lowest
    show_article = True
    shuffle_mode = True

    # Sound & Audio
    volume_limit = 0.1  # 0.0-1.0
    sound_enable = True
    sound_correct = _load_sound("correct-156911.mp3")
    sound_wrong = _load_sound("error-010-206498.mp3")