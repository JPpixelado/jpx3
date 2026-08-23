"""Tela de primeira inicialização da XMB-PY."""
from __future__ import annotations

import math
import random
import time
from pathlib import Path

import pygame

from xmb import theme
from xmb import audio as xmb_audio

ICON_PATH = Path(__file__).resolve().parent / "images" / "icon.png"


def run_first_boot(screen, clock, system_name="XMB-PY"):
    """Animação de primeira inicialização. Retorna True se o usuário fechou a janela."""
    w, h = screen.get_size()
    t0 = time.time()
    duration = 7.5  # segundos totais

    icon = None
    if ICON_PATH.is_file():
        try:
            icon = pygame.image.load(str(ICON_PATH)).convert_alpha()
            # escala para ~180px
            iw, ih = icon.get_size()
            scale = 180 / max(iw, ih)
            icon = pygame.transform.smoothscale(
                icon, (max(1, int(iw * scale)), max(1, int(ih * scale)))
            )
        except pygame.error:
            icon = None

    particles = [
        {
            "x": random.uniform(0, w),
            "y": random.uniform(0, h),
            "vx": random.uniform(-25, 25),
            "vy": random.uniform(-40, -8),
            "size": random.uniform(1.5, 4.0),
            "alpha": random.randint(40, 140),
        }
        for _ in range(90)
    ]

    xmb_audio.play("first_startup")

    quit_requested = False
    skip = False

    while True:
        dt = clock.tick(theme.FPS) / 1000.0
        elapsed = time.time() - t0
        t = min(1.0, elapsed / duration)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                quit_requested = True
                skip = True
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE, pygame.K_k):
                    skip = True
            elif event.type == pygame.JOYBUTTONDOWN:
                skip = True

        if skip and elapsed > 1.2:
            break
        if elapsed >= duration:
            break

        # fundo
        screen.fill((2, 4, 12))
        for y in range(0, h, 3):
            ratio = y / h
            c = (
                int(2 + 8 * ratio),
                int(4 + 12 * ratio),
                int(12 + 30 * ratio),
            )
            pygame.draw.rect(screen, c, (0, y, w, 3))

        # partículas
        for p in particles:
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            if p["y"] < -10:
                p["y"] = h + 10
                p["x"] = random.uniform(0, w)
            # brilho crescente no meio da animação
            phase = 0.4 + 0.6 * math.sin(elapsed * 2.0 + p["x"] * 0.01)
            a = int(p["alpha"] * phase * min(1.0, elapsed / 1.5))
            col = (120, 170, 255, max(0, min(255, a)))
            pygame.draw.circle(screen, col, (int(p["x"]), int(p["y"])), int(p["size"]))

        # ondas
        for i, (amp, yoff, speed, alpha) in enumerate([
            (22, 0.78, 0.35, 50),
            (16, 0.68, 0.45, 70),
            (10, 0.58, 0.55, 90),
        ]):
            pts = []
            for x in range(0, w + 24, 16):
                yy = h * yoff + math.sin(x * 0.008 + elapsed * speed * 5 + i) * amp
                pts.append((x, yy))
            pts += [(w, h), (0, h)]
            surf = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.polygon(surf, (40 + i * 15, 90 + i * 20, 180, alpha), pts)
            screen.blit(surf, (0, 0))

        # ícone com fade + glow
        icon_alpha = 0
        if elapsed < 1.5:
            icon_alpha = int(255 * (elapsed / 1.5))
        elif elapsed < duration - 1.2:
            icon_alpha = 255
        else:
            icon_alpha = int(255 * max(0, (duration - elapsed) / 1.2))

        cx, cy = w // 2, h // 2 - 30
        if icon is not None and icon_alpha > 0:
            # glow
            glow_r = 120 + int(20 * math.sin(elapsed * 3))
            glow = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
            pygame.draw.circle(glow, (80, 140, 255, min(80, icon_alpha // 3)), (glow_r, glow_r), glow_r)
            screen.blit(glow, (cx - glow_r, cy - glow_r))

            img = icon.copy()
            img.set_alpha(icon_alpha)
            screen.blit(img, img.get_rect(center=(cx, cy)))
        elif icon_alpha > 0:
            # fallback: círculo com XMB
            pygame.draw.circle(screen, (60, 120, 220), (cx, cy), 70)
            f = theme.font(28, bold=True)
            label = f.render("XMB", True, (240, 248, 255))
            screen.blit(label, label.get_rect(center=(cx, cy)))

        # texto do sistema
        text_alpha = 0
        if elapsed > 2.0:
            text_alpha = min(255, int(255 * (elapsed - 2.0) / 1.2))
        if elapsed > duration - 1.0:
            text_alpha = int(255 * max(0, (duration - elapsed) / 1.0))

        if text_alpha > 0:
            f_title = theme.font(36, bold=True)
            title = f_title.render(system_name, True, (230, 240, 255))
            title.set_alpha(text_alpha)
            screen.blit(title, title.get_rect(center=(cx, cy + 130)))

            f_sub = theme.font(16)
            sub = f_sub.render("Preparando o sistema…", True, (140, 160, 190))
            sub.set_alpha(text_alpha)
            screen.blit(sub, sub.get_rect(center=(cx, cy + 170)))

        # barra de progresso
        if elapsed > 0.8:
            bar_w = 280
            bar_h = 4
            bx = (w - bar_w) // 2
            by = h - 80
            prog = min(1.0, max(0.0, (elapsed - 0.8) / (duration - 1.5)))
            pygame.draw.rect(screen, (30, 45, 70), (bx, by, bar_w, bar_h), border_radius=2)
            pygame.draw.rect(
                screen, (90, 160, 255),
                (bx, by, int(bar_w * prog), bar_h),
                border_radius=2,
            )

        # dica pular
        if elapsed > 2.5:
            f_hint = theme.font(13)
            hint = f_hint.render("Pressione ✕ / Enter para continuar", True, (100, 115, 140))
            screen.blit(hint, hint.get_rect(center=(w // 2, h - 40)))

        pygame.display.flip()

    xmb_audio.stop("first_startup")
    return quit_requested


def run_startup(screen, clock, system_name="XMB-PY"):
    """Splash curto nas inicializações seguintes."""
    w, h = screen.get_size()
    t0 = time.time()
    xmb_audio.play("startup")

    icon = None
    if ICON_PATH.is_file():
        try:
            icon = pygame.image.load(str(ICON_PATH)).convert_alpha()
            iw, ih = icon.get_size()
            scale = 120 / max(iw, ih)
            icon = pygame.transform.smoothscale(
                icon, (max(1, int(iw * scale)), max(1, int(ih * scale)))
            )
        except pygame.error:
            icon = None

    while time.time() - t0 < 2.2:
        dt = clock.tick(theme.FPS) / 1000.0
        elapsed = time.time() - t0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return True
            if event.type == pygame.KEYDOWN and event.key in (
                pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE
            ):
                if elapsed > 0.6:
                    return False

        screen.fill((4, 8, 18))
        alpha = 255
        if elapsed < 0.4:
            alpha = int(255 * elapsed / 0.4)
        elif elapsed > 1.6:
            alpha = int(255 * max(0, (2.2 - elapsed) / 0.6))

        cx, cy = w // 2, h // 2 - 10
        if icon is not None:
            img = icon.copy()
            img.set_alpha(alpha)
            screen.blit(img, img.get_rect(center=(cx, cy)))

        f = theme.font(22, bold=True)
        t = f.render(system_name, True, (220, 230, 250))
        t.set_alpha(alpha)
        screen.blit(t, t.get_rect(center=(cx, cy + 90)))
        pygame.display.flip()

    return False
