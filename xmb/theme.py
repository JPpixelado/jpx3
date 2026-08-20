"""Tema visual inspirado na XMB (XrossMediaBar) do PlayStation 3 — versão aprimorada."""
import pygame

pygame.font.init()

# Cores — paleta mais rica e com maior contraste
BG_TOP = (4, 8, 22)
BG_BOTTOM = (0, 1, 6)
WAVE_COLOR_1 = (40, 90, 170)
WAVE_COLOR_2 = (22, 55, 115)
WAVE_COLOR_3 = (12, 30, 70)

TEXT_COLOR = (245, 248, 255)
TEXT_DIM = (155, 168, 195)
TEXT_MUTED = (100, 112, 140)

ICON_COLOR = (230, 238, 250)
ICON_DIM = (105, 118, 145)
HIGHLIGHT = (255, 255, 255)
ACCENT = (90, 165, 255)
ACCENT_SOFT = (55, 105, 190)
ACCENT_GLOW = (70, 140, 255)

PANEL_BG = (6, 14, 32, 230)
PANEL_BORDER = (75, 120, 195, 180)

OK_COLOR = (110, 225, 145)
ERROR_COLOR = (240, 95, 95)
WARNING_COLOR = (240, 190, 80)

# Fontes (usa fonte padrão do sistema, sem depender de arquivos externos)
_FONT_CACHE = {}


def font(size, bold=False):
    key = (size, bold)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = pygame.font.SysFont("segoeui,arial,sans-serif", size, bold=bold)
    return _FONT_CACHE[key]


FPS = 60
SCREEN_W = 1280
SCREEN_H = 720

ICON_SIZE = 68
ICON_SIZE_SELECTED = 98
ICON_GAP = 140

ITEM_SIZE = 46
ITEM_SIZE_SELECTED = 60
ITEM_GAP = 64
