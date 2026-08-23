"""Gerenciador de áudio da XMB-PY."""
from pathlib import Path
import pygame

ROOT = Path(__file__).resolve().parent.parent
AUDIO_DIR = ROOT / "audio"
SFX_DIR = AUDIO_DIR / "sfx"

_sounds = {}
_volume = 0.8
_ready = False


def init(volume_percent=80):
    global _ready, _volume
    _volume = max(0.0, min(1.0, volume_percent / 100.0))
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        _ready = True
        pygame.mixer.set_num_channels(16)
    except pygame.error:
        _ready = False
    _load_all()
    set_volume(volume_percent)


def _load(name, path):
    if not _ready or not path.is_file():
        return
    try:
        s = pygame.mixer.Sound(str(path))
        s.set_volume(_volume)
        _sounds[name] = s
    except pygame.error:
        pass


def _load_all():
    _load("first_startup", AUDIO_DIR / "first-startup.wav")
    _load("startup", SFX_DIR / "startup.wav")
    _load("shutdown", SFX_DIR / "shutdown.wav")
    _load("hover", SFX_DIR / "hover.mp3")
    _load("select", SFX_DIR / "select.mp3")
    _load("confirm", SFX_DIR / "confirm-cancel.mp3")
    _load("popup", SFX_DIR / "popup.mp3")


def set_volume(percent):
    global _volume
    _volume = max(0.0, min(1.0, int(percent) / 100.0))
    for s in _sounds.values():
        try:
            s.set_volume(_volume)
        except pygame.error:
            pass
    try:
        if pygame.mixer.get_init():
            pygame.mixer.music.set_volume(_volume)
    except pygame.error:
        pass


def play(name):
    if not _ready:
        return
    s = _sounds.get(name)
    if s:
        try:
            s.play()
        except pygame.error:
            pass


def stop(name=None):
    if not _ready:
        return
    try:
        if name and name in _sounds:
            _sounds[name].stop()
        else:
            pygame.mixer.stop()
    except pygame.error:
        pass
