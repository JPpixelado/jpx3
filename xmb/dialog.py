"""Diálogos modais simples para a XMB (login / registro / confirmação)."""
import pygame

from . import theme


def _draw_panel(surface, px, py, pw, ph):
    shadow = pygame.Surface((pw + 16, ph + 16), pygame.SRCALPHA)
    pygame.draw.rect(shadow, (0, 0, 0, 100), (8, 8, pw, ph), border_radius=14)
    surface.blit(shadow, (px - 8, py - 8))
    panel = pygame.Surface((pw, ph), pygame.SRCALPHA)
    pygame.draw.rect(panel, theme.PANEL_BG, (0, 0, pw, ph), border_radius=14)
    pygame.draw.rect(panel, theme.PANEL_BORDER, (0, 0, pw, ph), width=2, border_radius=14)
    surface.blit(panel, (px, py))


def text_input_dialog(screen, clock, title, fields, submit_label="Confirmar"):
    """Diálogo de formulário com campos de texto.

    fields: lista de dicts {"key", "label", "password": bool, "value": str}
    Retorna dict com os valores preenchidos, ou None se cancelado.
    """
    w, h = screen.get_size()
    # Cópia do fundo atual
    bg = screen.copy()

    field_values = [f.get("value", "") for f in fields]
    active = 0
    error_msg = None
    cursor_blink = 0

    panel_w = 480
    panel_h = 140 + len(fields) * 72 + 60
    px = (w - panel_w) // 2
    py = (h - panel_h) // 2

    while True:
        dt = clock.tick(theme.FPS)
        cursor_blink = (cursor_blink + dt) % 1000

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_l):
                    return None
                if event.key == pygame.K_TAB:
                    active = (active + 1) % len(fields)
                elif event.key == pygame.K_UP:
                    active = (active - 1) % len(fields)
                elif event.key == pygame.K_DOWN:
                    active = (active + 1) % len(fields)
                elif event.key == pygame.K_RETURN:
                    # Validação mínima
                    if all(v.strip() for v in field_values):
                        return {fields[i]["key"]: field_values[i].strip() for i in range(len(fields))}
                    error_msg = "Preencha todos os campos."
                elif event.key == pygame.K_BACKSPACE:
                    field_values[active] = field_values[active][:-1]
                    error_msg = None
                else:
                    ch = event.unicode
                    if ch and ch.isprintable() and len(field_values[active]) < 48:
                        field_values[active] += ch
                        error_msg = None

        screen.blit(bg, (0, 0))
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))

        _draw_panel(screen, px, py, panel_w, panel_h)

        f_title = theme.font(24, bold=True)
        t = f_title.render(title, True, theme.TEXT_COLOR)
        screen.blit(t, (px + (panel_w - t.get_width()) // 2, py + 22))

        y = py + 70
        for i, field in enumerate(fields):
            f_label = theme.font(14)
            lbl = f_label.render(field["label"], True, theme.TEXT_DIM)
            screen.blit(lbl, (px + 40, y))

            box_rect = pygame.Rect(px + 40, y + 22, panel_w - 80, 36)
            is_active = i == active
            border_col = theme.ACCENT if is_active else theme.PANEL_BORDER
            pygame.draw.rect(screen, (10, 18, 40), box_rect, border_radius=8)
            pygame.draw.rect(screen, border_col, box_rect, width=2, border_radius=8)

            display = field_values[i]
            if field.get("password"):
                display = "•" * len(display)
            if is_active and cursor_blink < 500:
                display += "|"

            f_val = theme.font(18)
            val_surf = f_val.render(display, True, theme.TEXT_COLOR)
            screen.blit(val_surf, (box_rect.x + 12, box_rect.y + 8))
            y += 72

        if error_msg:
            f_err = theme.font(14)
            err = f_err.render(error_msg, True, theme.ERROR_COLOR)
            screen.blit(err, (px + (panel_w - err.get_width()) // 2, y))

        f_hint = theme.font(13)
        hint = f_hint.render("Tab/↑↓ campos   Enter confirmar   Esc cancelar", True, theme.TEXT_MUTED)
        screen.blit(hint, (px + (panel_w - hint.get_width()) // 2, py + panel_h - 32))

        pygame.display.flip()


def confirm_dialog(screen, clock, title, message, yes_label="Sim", no_label="Não"):
    """Diálogo de confirmação. Retorna True (sim), False (não) ou None (fechou)."""
    w, h = screen.get_size()
    bg = screen.copy()
    selected = 0  # 0 = sim, 1 = não

    panel_w, panel_h = 440, 200
    px = (w - panel_w) // 2
    py = (h - panel_h) // 2

    while True:
        clock.tick(theme.FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_l):
                    return False
                if event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_a, pygame.K_d, pygame.K_TAB):
                    selected = 1 - selected
                if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_k):
                    return selected == 0

        screen.blit(bg, (0, 0))
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))
        _draw_panel(screen, px, py, panel_w, panel_h)

        f_title = theme.font(22, bold=True)
        t = f_title.render(title, True, theme.TEXT_COLOR)
        screen.blit(t, (px + (panel_w - t.get_width()) // 2, py + 24))

        f_msg = theme.font(16)
        # wrap simples
        words = message.split()
        lines, cur = [], ""
        for word in words:
            trial = f"{cur} {word}".strip()
            if f_msg.size(trial)[0] > panel_w - 60 and cur:
                lines.append(cur)
                cur = word
            else:
                cur = trial
        if cur:
            lines.append(cur)
        my = py + 70
        for line in lines[:3]:
            s = f_msg.render(line, True, theme.TEXT_DIM)
            screen.blit(s, (px + (panel_w - s.get_width()) // 2, my))
            my += 22

        # Botões
        btn_y = py + panel_h - 55
        for i, label in enumerate([yes_label, no_label]):
            bx = px + 60 + i * 180
            is_sel = i == selected
            col = theme.ACCENT if is_sel else theme.TEXT_DIM
            f = theme.font(18, bold=is_sel)
            s = f.render(label, True, col)
            if is_sel:
                pygame.draw.rect(screen, (*theme.ACCENT, 40), (bx - 10, btn_y - 6, s.get_width() + 20, 32), border_radius=8)
            screen.blit(s, (bx, btn_y))

        pygame.display.flip()


def choice_dialog(screen, clock, title, options):
    """Menu de opções vertical.

    options: lista de (key, label)  ex.: [("play", "Jogar"), ("uninstall", "Desinstalar")]
    Retorna a key escolhida, ou None se cancelar / fechar.
    """
    w, h = screen.get_size()
    bg = screen.copy()
    selected = 0
    n = len(options)

    panel_w = 420
    panel_h = 110 + n * 48
    px = (w - panel_w) // 2
    py = (h - panel_h) // 2

    while True:
        clock.tick(theme.FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_l):
                    return None
                if event.key in (pygame.K_UP, pygame.K_w):
                    selected = (selected - 1) % n
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    selected = (selected + 1) % n
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_k):
                    return options[selected][0]

        screen.blit(bg, (0, 0))
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))
        _draw_panel(screen, px, py, panel_w, panel_h)

        f_title = theme.font(22, bold=True)
        t = f_title.render(title, True, theme.TEXT_COLOR)
        screen.blit(t, (px + (panel_w - t.get_width()) // 2, py + 20))

        y = py + 70
        for i, (key, label) in enumerate(options):
            is_sel = i == selected
            color = theme.TEXT_COLOR if is_sel else theme.TEXT_DIM
            f = theme.font(18, bold=is_sel)
            s = f.render(label, True, color)
            if is_sel:
                pygame.draw.polygon(
                    screen, theme.ACCENT,
                    [(px + 36, y + 4), (px + 36, y + 18), (px + 48, y + 11)]
                )
            screen.blit(s, (px + 60, y))
            y += 44

        f_hint = theme.font(12)
        hint = f_hint.render("↑ ↓   Enter confirmar   Esc cancelar", True, theme.TEXT_MUTED)
        screen.blit(hint, (px + (panel_w - hint.get_width()) // 2, py + panel_h - 28))
        pygame.display.flip()
