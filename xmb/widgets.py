"""Ícones vetoriais simples desenhados via pygame.draw, sem depender de imagens externas."""
import math
import pygame

from . import theme


def draw_icon(surface, kind, center, size, color, alpha=255):
    """Desenha um ícone de 'kind' centralizado em 'center' com tamanho 'size'."""
    s = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
    c = (size, size)
    r = size * 0.42

    col = (*color, alpha) if len(color) == 3 else color

    if kind == "user":
        pygame.draw.circle(s, col, (c[0], c[1] - r * 0.35), r * 0.42)
        pygame.draw.ellipse(
            s, col,
            (c[0] - r, c[1] + r * 0.05, r * 2, r * 1.15)
        )
    elif kind == "settings":
        pygame.draw.circle(s, col, c, r * 0.9, width=max(2, int(size * 0.09)))
        pygame.draw.circle(s, col, c, r * 0.32)
        for i in range(8):
            ang = i * (math.pi / 4)
            x1 = c[0] + math.cos(ang) * r * 0.95
            y1 = c[1] + math.sin(ang) * r * 0.95
            x2 = c[0] + math.cos(ang) * r * 1.25
            y2 = c[1] + math.sin(ang) * r * 1.25
            pygame.draw.line(s, col, (x1, y1), (x2, y2), max(2, int(size * 0.09)))
    elif kind == "photo":
        rect = pygame.Rect(0, 0, r * 2.1, r * 1.6)
        rect.center = c
        pygame.draw.rect(s, col, rect, width=max(2, int(size * 0.08)), border_radius=4)
        pygame.draw.circle(s, col, (int(c[0] - r * 0.5), int(c[1] - r * 0.15)), r * 0.28)
        pts = [(rect.left + 6, rect.bottom - 6), (c[0] - 5, c[1]), (c[0] + r * 0.4, c[1] + r * 0.35),
               (rect.right - 6, rect.top + r * 0.5), (rect.right - 6, rect.bottom - 6)]
        pygame.draw.polygon(s, col, pts)
    elif kind == "music":
        pygame.draw.circle(s, col, (int(c[0] - r * 0.5), int(c[1] + r * 0.55)), r * 0.3)
        pygame.draw.circle(s, col, (int(c[0] + r * 0.55), int(c[1] + r * 0.35)), r * 0.3)
        pygame.draw.line(s, col, (c[0] - r * 0.5 + r * 0.28, c[1] + r * 0.4),
                          (c[0] - r * 0.5 + r * 0.28, c[1] - r * 0.9), max(2, int(size * 0.09)))
        pygame.draw.line(s, col, (c[0] + r * 0.55 + r * 0.28, c[1] + r * 0.2),
                          (c[0] + r * 0.55 + r * 0.28, c[1] - r * 1.05), max(2, int(size * 0.09)))
        pygame.draw.line(s, col, (c[0] - r * 0.5 + r * 0.28, c[1] - r * 0.9),
                          (c[0] + r * 0.55 + r * 0.28, c[1] - r * 1.05), max(2, int(size * 0.09)))
    elif kind == "video":
        rect = pygame.Rect(0, 0, r * 2.1, r * 1.5)
        rect.center = c
        pygame.draw.rect(s, col, rect, width=max(2, int(size * 0.08)), border_radius=4)
        tri = [(c[0] - r * 0.28, c[1] - r * 0.4), (c[0] - r * 0.28, c[1] + r * 0.4), (c[0] + r * 0.45, c[1])]
        pygame.draw.polygon(s, col, tri)
    elif kind == "game":
        rect = pygame.Rect(0, 0, r * 2.2, r * 1.3)
        rect.center = c
        pygame.draw.rect(s, col, rect, border_radius=int(r * 0.6))
        bg = (int(theme.BG_TOP[0]), int(theme.BG_TOP[1]), int(theme.BG_TOP[2]), alpha)
        pygame.draw.circle(s, bg, (int(c[0] - r * 0.65), int(c[1])), r * 0.16)
        pygame.draw.circle(s, bg, (int(c[0] - r * 0.35), int(c[1])), r * 0.16)
        pygame.draw.line(s, bg, (c[0] - r * 0.5, c[1] - r * 0.16), (c[0] - r * 0.5, c[1] + r * 0.16), 3)
        pygame.draw.circle(s, bg, (int(c[0] + r * 0.5), int(c[1] - r * 0.18)), r * 0.13)
        pygame.draw.circle(s, bg, (int(c[0] + r * 0.75), int(c[1] + r * 0.05)), r * 0.13)
    elif kind == "store":
        rect = pygame.Rect(0, 0, r * 1.9, r * 1.5)
        rect.center = (c[0], c[1] + r * 0.25)
        pygame.draw.rect(s, col, rect, width=max(2, int(size * 0.08)), border_radius=4)
        pygame.draw.arc(s, col, (c[0] - r * 0.75, c[1] - r * 1.1, r * 1.5, r * 1.3),
                         math.pi, 2 * math.pi, max(2, int(size * 0.09)))
    elif kind == "network":
        for i, rad in enumerate([r * 0.4, r * 0.75, r * 1.05]):
            start = math.pi * 1.25
            end = math.pi * 1.75
            pygame.draw.arc(s, col, (c[0] - rad, c[1] - rad * 0.4, rad * 2, rad * 2), start, end,
                             max(2, int(size * 0.09)))
        pygame.draw.circle(s, col, (c[0], c[1] + r * 0.55), r * 0.14)
    elif kind == "friends":
        pygame.draw.circle(s, col, (int(c[0] - r * 0.4), int(c[1] - r * 0.25)), r * 0.32)
        pygame.draw.ellipse(s, col, (c[0] - r * 1.05, c[1] + r * 0.1, r * 1.3, r * 0.95))
        pygame.draw.circle(s, col, (int(c[0] + r * 0.45), int(c[1] - r * 0.2)), r * 0.3)
        pygame.draw.ellipse(s, col, (c[0] - r * 0.15, c[1] + r * 0.1, r * 1.3, r * 0.95))
    elif kind == "power":
        pygame.draw.circle(s, col, c, r * 0.75, width=max(2, int(size * 0.1)))
        pygame.draw.line(s, col, (c[0], c[1] - r * 1.05), (c[0], c[1] - r * 0.1), max(2, int(size * 0.1)))
    else:  # generic
        pygame.draw.circle(s, col, c, r * 0.8, width=max(2, int(size * 0.09)))

    surface.blit(s, (center[0] - size, center[1] - size))
