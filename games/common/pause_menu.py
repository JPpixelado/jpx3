"""Menu de pausa padrão para jogos do XMB-PY.

Pressione ESC dentro de um jogo para abrir este menu. Opções:
  - Continuar
  - Sair do jogo
  - Imagens
  - Vídeos

A lista acompanha a seleção: a opção ativa permanece na zona de foco.
"""
import pygame

from xmb import theme


OPTIONS = [
    ("resume", "Continuar", "Retorna ao jogo"),
    ("quit", "Sair do jogo", "Volta para a XMB"),
    ("images", "Imagens", "Galeria de capturas e fotos"),
    ("videos", "Vídeos", "Biblioteca de vídeos"),
]


def show_pause_menu(screen, clock):
    """Exibe o menu de pausa modal e retorna a escolha do usuário.

    Retornos: "resume", "quit", "images", "videos".
    """
    w, h = screen.get_size()
    selected = 0
    anim = 0.0

    panel_w, panel_h = 440, 320
    px = (w - panel_w) // 2
    py = (h - panel_h) // 2

    # Captura o frame atual como fundo
    bg = screen.copy()

    while True:
        dt = clock.tick(theme.FPS) / 1000.0
        anim += (selected - anim) * min(1.0, dt * 14)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_UP, pygame.K_w):
                    selected = (selected - 1) % len(OPTIONS)
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    selected = (selected + 1) % len(OPTIONS)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    return OPTIONS[selected][0]
                elif event.key == pygame.K_ESCAPE:
                    return "resume"

        screen.blit(bg, (0, 0))
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        # Painel
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        pygame.draw.rect(panel, theme.PANEL_BG, (0, 0, panel_w, panel_h), border_radius=16)
        pygame.draw.rect(panel, theme.PANEL_BORDER, (0, 0, panel_w, panel_h), width=2, border_radius=16)
        screen.blit(panel, (px, py))

        f_title = theme.font(24, bold=True)
        title = f_title.render("Menu de Pausa", True, theme.TEXT_COLOR)
        screen.blit(title, (px + (panel_w - title.get_width()) // 2, py + 20))

        pygame.draw.line(
            screen, (*theme.ACCENT_SOFT, 140),
            (px + 36, py + 58), (px + panel_w - 36, py + 58), 1
        )

        # Zona de lista com clipping visual
        list_top = py + 72
        list_bottom = py + panel_h - 44
        list_h = list_bottom - list_top
        focus_y = list_top + list_h * 0.42
        gap = 54

        for i, (key, label, subtitle) in enumerate(OPTIONS):
            offset = i - anim
            y = focus_y + offset * gap
            if y < list_top - 20 or y > list_bottom + 20:
                continue

            dist = abs(offset)
            is_sel = dist < 0.08
            color = theme.TEXT_COLOR if is_sel else theme.TEXT_DIM
            f = theme.font(20 if is_sel else 17, bold=is_sel)
            txt = f.render(label, True, color)
            tx = px + 70

            if is_sel:
                bg_w = panel_w - 48
                hl = pygame.Surface((bg_w, 44), pygame.SRCALPHA)
                pygame.draw.rect(hl, (*theme.ACCENT, 30), (0, 0, bg_w, 44), border_radius=10)
                surface_y = int(y - 22)
                screen.blit(hl, (px + 24, surface_y))
                pygame.draw.polygon(
                    screen, theme.ACCENT,
                    [(px + 40, int(y) - 7), (px + 40, int(y) + 7), (px + 52, int(y))]
                )

            screen.blit(txt, (tx, int(y - txt.get_height() / 2)))
            if is_sel:
                f_sub = theme.font(12)
                sub = f_sub.render(subtitle, True, theme.TEXT_MUTED)
                screen.blit(sub, (tx, int(y + txt.get_height() / 2)))

        f_hint = theme.font(12)
        hint = f_hint.render("↑ ↓ navegar   Enter confirmar   Esc continuar", True, theme.TEXT_MUTED)
        screen.blit(hint, (px + (panel_w - hint.get_width()) // 2, py + panel_h - 28))

        pygame.display.flip()
