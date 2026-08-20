"""Interface completa da Loja Online — visual inspirado na PS Store / XMB do PS3.

Aberta pelo item "Entrar na Store" na categoria Loja Online.
"""
from __future__ import annotations

import math
import time
from pathlib import Path

import pygame

from xmb import theme
from xmb.widgets import draw_icon
from xmb.dialog import confirm_dialog
from store.client import StoreClient, StoreError
from store import session as sess


# Layout
COLS = 3
CARD_W, CARD_H = 280, 160
CARD_GAP_X, CARD_GAP_Y = 28, 24


def _wrap(text, font_obj, max_w):
    words = (text or "").split()
    lines, cur = [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if font_obj.size(trial)[0] > max_w and cur:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


class StoreUI:
    """Loja em tela cheia com grid de produtos estilo PS3."""

    def __init__(self, screen, clock, store_client: StoreClient, on_install_game=None, on_install_wallpaper=None):
        self.screen = screen
        self.clock = clock
        self.client = store_client
        self.on_install_game = on_install_game
        self.on_install_wallpaper = on_install_wallpaper

        self.items = []
        self.loading = True
        self.error = None
        self.selected = 0
        self.scroll = 0.0  # linha de scroll animada
        self.mode = "grid"  # grid | detail
        self.message = None
        self.message_until = 0
        self.t0 = time.time()
        self.running = True
        self.quit_app = False

        self._load_items()

    def _load_items(self):
        self.loading = True
        self.error = None
        try:
            raw = self.client.get_items_raw()
            self.items = raw
            self.loading = False
        except StoreError as exc:
            # fallback mock
            try:
                from store import mock_data
                self.items = mock_data.MOCK_ITEMS
                self.error = None
            except Exception:
                self.items = []
                self.error = str(exc)
            self.loading = False
        self.selected = min(self.selected, max(0, len(self.items) - 1))

    def flash(self, text, seconds=2.5):
        self.message = text
        self.message_until = time.time() + seconds

    def run(self):
        """Loop principal. Retorna True se o app inteiro deve fechar."""
        while self.running:
            dt = self.clock.tick(theme.FPS) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.quit_app = True
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    self._handle_key(event.key)

            target_row = self.selected // COLS if self.items else 0
            self.scroll += (target_row - self.scroll) * min(1.0, dt * 10)

            if self.message and time.time() > self.message_until:
                self.message = None

            self._draw()
            pygame.display.flip()

        return self.quit_app

    def _handle_key(self, key):
        if self.mode == "grid":
            if key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                self.running = False
            elif not self.items:
                return
            elif key in (pygame.K_RIGHT, pygame.K_d):
                self.selected = min(len(self.items) - 1, self.selected + 1)
            elif key in (pygame.K_LEFT, pygame.K_a):
                self.selected = max(0, self.selected - 1)
            elif key in (pygame.K_DOWN, pygame.K_s):
                self.selected = min(len(self.items) - 1, self.selected + COLS)
            elif key in (pygame.K_UP, pygame.K_w):
                self.selected = max(0, self.selected - COLS)
            elif key in (pygame.K_RETURN, pygame.K_SPACE):
                self.mode = "detail"
            elif key == pygame.K_r:
                self._load_items()
                self.flash("Catálogo atualizado.")
        elif self.mode == "detail":
            if key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                self.mode = "grid"
            elif key in (pygame.K_RETURN, pygame.K_SPACE):
                self._purchase_selected()

    def _purchase_selected(self):
        if not self.items:
            return
        data = self.items[self.selected]
        name = data.get("name", "?")
        item_id = data["id"]
        has_file = bool(data.get("has_file"))
        cat = (data.get("category") or "").lower()
        icon = (data.get("icon") or "").lower()
        is_wallpaper = cat in ("tema", "wallpaper", "foto", "photo") or icon == "photo"
        is_game = cat in ("jogo", "game") or icon == "game"

        try:
            user = sess.get_user()
            result = self.client.purchase(
                item_id, user=(user or {}).get("username", "convidado")
            )
            msg = result.get("message", f"'{name}' adquirido!")

            if has_file:
                self.flash("Baixando…")
                pygame.display.flip()
                content = self.client.download_item_file(item_id)
                if content and content[:2] == b"PK":
                    self.flash("Extraindo jogo…")
                    pygame.display.flip()
                    dest = self.client.install_game(item_id, name)
                    if self.on_install_game:
                        self.on_install_game(dest)
                    self.flash(f"Jogo instalado: {Path(dest).name}")
                elif content and (
                    content[:4] == b"\x89PNG"
                    or content[:3] == b"\xff\xd8\xff"
                    or is_wallpaper
                ):
                    path = self.client.install_wallpaper(item_id)
                    apply = confirm_dialog(
                        self.screen, self.clock,
                        "Wallpaper baixado",
                        f"Aplicar '{name}' agora?",
                        yes_label="Aplicar", no_label="Depois",
                    )
                    if apply and self.on_install_wallpaper:
                        self.on_install_wallpaper(path)
                        self.flash(f"Wallpaper '{name}' aplicado!")
                    else:
                        self.flash(f"Salvo em wallpapers/.")
                else:
                    self.flash(msg)
            else:
                self.flash(msg)
        except StoreError as exc:
            self.flash(f"Falha: {exc}")

    # ---------- draw ----------

    def _draw(self):
        w, h = self.screen.get_size()
        self._draw_background(w, h)
        self._draw_header(w, h)

        if self.loading:
            f = theme.font(22)
            t = f.render("Carregando catálogo…", True, theme.TEXT_DIM)
            self.screen.blit(t, (w // 2 - t.get_width() // 2, h // 2))
        elif self.error and not self.items:
            f = theme.font(18)
            t = f.render(f"Erro: {self.error}", True, theme.ERROR_COLOR)
            self.screen.blit(t, (w // 2 - t.get_width() // 2, h // 2))
        elif self.mode == "grid":
            self._draw_grid(w, h)
        else:
            self._draw_detail(w, h)

        self._draw_footer(w, h)
        if self.message:
            self._draw_message(w, h)

    def _draw_background(self, w, h):
        # Gradiente escuro estilo PS3
        top = pygame.Color(8, 14, 32)
        bottom = pygame.Color(2, 4, 12)
        for y in range(0, h, 3):
            col = top.lerp(bottom, y / h)
            pygame.draw.rect(self.screen, col, (0, y, w, 3))

        # Ondas sutis
        t = time.time() - self.t0
        for i, (amp, yoff, speed, alpha) in enumerate([
            (18, 0.82, 0.2, 40),
            (12, 0.72, 0.28, 55),
        ]):
            pts = []
            for x in range(0, w + 24, 20):
                yy = h * yoff + math.sin(x * 0.006 + t * speed * 4 + i) * amp
                pts.append((x, yy))
            pts += [(w, h), (0, h)]
            surf = pygame.Surface((w, h), pygame.SRCALPHA)
            color = (40 + i * 20, 80 + i * 25, 160, alpha)
            pygame.draw.polygon(surf, color, pts)
            self.screen.blit(surf, (0, 0))

    def _draw_header(self, w, h):
        # Barra superior
        bar = pygame.Surface((w, 72), pygame.SRCALPHA)
        bar.fill((6, 12, 28, 210))
        self.screen.blit(bar, (0, 0))
        pygame.draw.line(self.screen, (*theme.ACCENT_SOFT, 120), (0, 72), (w, 72), 1)

        f_title = theme.font(28, bold=True)
        title = f_title.render("XMB Store", True, theme.TEXT_COLOR)
        self.screen.blit(title, (40, 20))

        # Badge do usuário
        user = sess.get_user()
        f_u = theme.font(14)
        if user:
            label = f"● {user.get('display_name') or user.get('username')}"
            col = theme.OK_COLOR
        else:
            label = "Convidado"
            col = theme.TEXT_DIM
        us = f_u.render(label, True, col)
        self.screen.blit(us, (w - us.get_width() - 40, 28))

        # Contador
        f_c = theme.font(14)
        cnt = f_c.render(f"{len(self.items)} itens", True, theme.TEXT_MUTED)
        self.screen.blit(cnt, (40 + title.get_width() + 24, 30))

    def _draw_grid(self, w, h):
        if not self.items:
            f = theme.font(20)
            t = f.render("Catálogo vazio", True, theme.TEXT_MUTED)
            self.screen.blit(t, (w // 2 - t.get_width() // 2, h // 2))
            return

        margin_x = 48
        top = 100
        # quantas colunas cabem
        cols = max(1, min(COLS, (w - margin_x * 2 + CARD_GAP_X) // (CARD_W + CARD_GAP_X)))
        # recalcula selected navigation was fixed at COLS=3; keep visual cols aligned
        grid_w = cols * CARD_W + (cols - 1) * CARD_GAP_X
        start_x = (w - grid_w) // 2

        for i, data in enumerate(self.items):
            row = i // cols
            col = i % cols
            x = start_x + col * (CARD_W + CARD_GAP_X)
            y = top + (row - self.scroll) * (CARD_H + CARD_GAP_Y)

            if y + CARD_H < top - 20 or y > h - 40:
                continue

            is_sel = i == self.selected
            self._draw_card(x, y, data, is_sel)

    def _draw_card(self, x, y, data, selected):
        card = pygame.Surface((CARD_W, CARD_H), pygame.SRCALPHA)
        bg = (12, 22, 48, 230) if selected else (10, 18, 38, 200)
        border = theme.ACCENT if selected else (50, 80, 140, 160)
        pygame.draw.rect(card, bg, (0, 0, CARD_W, CARD_H), border_radius=14)
        pygame.draw.rect(card, border, (0, 0, CARD_W, CARD_H), width=2 if selected else 1, border_radius=14)

        if selected:
            # brilho superior
            glow = pygame.Surface((CARD_W, 40), pygame.SRCALPHA)
            pygame.draw.rect(glow, (*theme.ACCENT, 35), (0, 0, CARD_W, 40), border_radius=14)
            card.blit(glow, (0, 0))

        self.screen.blit(card, (x, y))

        icon = data.get("icon") or "store"
        draw_icon(self.screen, icon, (x + 40, y + 48), 28, theme.ICON_COLOR)

        f_name = theme.font(18, bold=True)
        name = data.get("name", "")
        # corta nome longo
        while f_name.size(name)[0] > CARD_W - 90 and len(name) > 3:
            name = name[:-2]
        if name != data.get("name", ""):
            name = name[:-1] + "…"
        ns = f_name.render(name, True, theme.TEXT_COLOR)
        self.screen.blit(ns, (x + 78, y + 28))

        f_cat = theme.font(13)
        cat = f_cat.render(data.get("category") or "", True, theme.TEXT_DIM)
        self.screen.blit(cat, (x + 78, y + 54))

        price = str(data.get("price") or "")
        f_price = theme.font(16, bold=True)
        ps = f_price.render(price, True, theme.OK_COLOR)
        self.screen.blit(ps, (x + 20, y + CARD_H - 36))

        if data.get("has_file"):
            f_dl = theme.font(12)
            dl = f_dl.render("BAIXÁVEL", True, theme.ACCENT)
            self.screen.blit(dl, (x + CARD_W - dl.get_width() - 16, y + CARD_H - 34))

    def _draw_detail(self, w, h):
        data = self.items[self.selected]
        panel_w, panel_h = min(720, w - 80), min(400, h - 120)
        px = (w - panel_w) // 2
        py = (h - panel_h) // 2

        shadow = pygame.Surface((panel_w + 24, panel_h + 24), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 100), (12, 12, panel_w, panel_h), border_radius=18)
        self.screen.blit(shadow, (px - 12, py - 12))

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        pygame.draw.rect(panel, (8, 16, 36, 240), (0, 0, panel_w, panel_h), border_radius=18)
        pygame.draw.rect(panel, theme.PANEL_BORDER, (0, 0, panel_w, panel_h), width=2, border_radius=18)
        self.screen.blit(panel, (px, py))

        icon = data.get("icon") or "store"
        draw_icon(self.screen, icon, (px + 70, py + 70), 40, theme.ICON_COLOR)

        f_title = theme.font(28, bold=True)
        title = f_title.render(data.get("name", ""), True, theme.TEXT_COLOR)
        self.screen.blit(title, (px + 130, py + 36))

        f_sub = theme.font(16)
        sub = f_sub.render(data.get("category") or "", True, theme.TEXT_DIM)
        self.screen.blit(sub, (px + 130, py + 74))

        f_desc = theme.font(16)
        y = py + 130
        for line in _wrap(data.get("description") or "", f_desc, panel_w - 80)[:6]:
            s = f_desc.render(line, True, theme.TEXT_COLOR)
            self.screen.blit(s, (px + 40, y))
            y += 24

        price = str(data.get("price") or "")
        f_price = theme.font(24, bold=True)
        ps = f_price.render(price, True, theme.OK_COLOR)
        self.screen.blit(ps, (px + 40, py + panel_h - 56))

        f_hint = theme.font(14)
        hint = f_hint.render("Enter: comprar / baixar    Esc: voltar", True, theme.TEXT_MUTED)
        self.screen.blit(hint, (px + panel_w - hint.get_width() - 28, py + panel_h - 40))

    def _draw_footer(self, w, h):
        f = theme.font(13)
        if self.mode == "grid":
            hint = "← → ↑ ↓ navegar    Enter detalhes    R atualizar    Esc voltar à XMB"
        else:
            hint = "Enter comprar    Esc voltar ao catálogo"
        t = f.render(hint, True, theme.TEXT_MUTED)
        self.screen.blit(t, (40, h - 32))

    def _draw_message(self, w, h):
        f = theme.font(16, bold=True)
        txt = f.render(self.message, True, theme.TEXT_COLOR)
        pad = 16
        box = pygame.Surface((txt.get_width() + pad * 2, txt.get_height() + pad * 2), pygame.SRCALPHA)
        pygame.draw.rect(box, theme.PANEL_BG, box.get_rect(), border_radius=12)
        pygame.draw.rect(box, theme.PANEL_BORDER, box.get_rect(), width=2, border_radius=12)
        box.blit(txt, (pad, pad))
        self.screen.blit(box, (w / 2 - box.get_width() / 2, h - 100))
