from modes_and_logics.main_settings import Settings

settings=Settings()


# Load sounds
sound_correct=Settings.sound_correct
sound_wrong=Settings.sound_wrong
if Settings.sound_enable:
    sound_correct.set_volume(Settings.volume_limit)
    sound_wrong.set_volume(Settings.volume_limit)
else:
    sound_correct.set_volume(0.0)
    sound_wrong.set_volume(0.0)