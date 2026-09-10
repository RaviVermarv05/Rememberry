import pygame
pygame.init()

# Initialize the mixer
pygame.mixer.init()
class Settings:

    # Quiz Settings
    trials=2 #1 being the lowest
    show_article=True
    shuffle_mode=True

    # Sound & Audio
    volume_limit=0.1  #0.0-1.0
    sound_enable=True
    sound_correct = pygame.mixer.Sound("/Users/raviverma/PycharmProjects/german vocab/sound/correct-156911.mp3")
    sound_wrong = pygame.mixer.Sound("/Users/raviverma/PycharmProjects/german vocab/sound/error-010-206498.mp3")


