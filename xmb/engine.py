"""Núcleo da interface estilo XMB (PS3): navegação horizontal por categorias
e vertical por itens, com painel de detalhes, partículas sutis e suporte a
carregamento assíncrono de itens (usado pela categoria de Loja Online)."""
import math
import time
import threading
import datetime
import random

import pygame

from . import theme
from .widgets import draw_icon


class Item:
    def __init__(self, item_id, name, subtitle="", icon="generic", payload=None, action=None):
        self.id = item_id
        self.name = name
        self.subtitle = subtitle
        self.icon = icon
        self.payload = payload or {}
        self.action = action  # callable(engine, item) -> chamado ao confirmar


class Category:
    def __init__(self, cat_id, name, icon, items=None, loader=None):
        self.id = cat_id
        self.name = name
        self.icon = icon
        self.items = items or []
        self.loader = loader  # callable() -> list[Item] (rodado em thread)
        self.loading = False
        self.load_error = None
        self.loaded_once = False

    def trigger_load(self):
        if self.loader is None or self.loaded_once or self.loading:
            return
        self.loading = True
        self.load_error = None

        def worker():
            try:
                new_items = self.loader()
                self.items = new_items
            except Exception as exc:  # noqa: BLE001
                self.load_error = str(exc)
            finally:
                self.loading = False
                self.loaded_once = True

        threading.Thread(target=worker, daemon=True).start()


class XMBEngine:
    def __init__(self, screen, categories, system_name="XMB-PY", wallpaper_path=None):
        self.screen = screen
        self.categories = categories
        self.system_name = system_name

        self.cat_index = 0
        self.item_index = {cat.id: 0 for cat in categories}

        self.mode = "browse"  # browse | detail
        self.message = None
        self.message_until = 0

        self.cat_anim = 0.0
        self.item_anim = {}

        self.t0 = time.time()
        self.running = True

        # Wallpaper personalizado (None = gradiente padrão)
        self._wallpaper_path = None
        self._wallpaper_surf = None
        self.set_wallpaper(wallpaper_path)

        # Nome do usuário logado (exibido no canto)
        self.user_display = None

        # Partículas de fundo (pontos sutis)
        self.particles = [
            {
                "x": random.uniform(0, theme.SCREEN_W),
                "y": random.uniform(0, theme.SCREEN_H),
                "speed": random.uniform(8, 28),
                "size": random.uniform(1.0, 2.5),
                "alpha": random.randint(40, 110),
            }
            for _ in range(55)
        ]

        self.categories[self.cat_index].trigger_load()

    def set_wallpaper(self, path):
        """Define ou remove o papel de parede. path=None restaura o gradiente."""
        self._wallpaper_path = path
        self._wallpaper_surf = None
        if path:
            try:
                img = pygame.image.load(path).convert()
                self._wallpaper_surf = img
            except (pygame.error, OSError):
                self._wallpaper_path = None
                self._wallpaper_surf = None

    # ---------- utilidades ----------

    def current_category(self):
        return self.categories[self.cat_index]

    def current_items(self):
        return self.current_category().items

    def selected_item(self):
        items = self.current_items()
        cat = self.current_category()
        idx = self.item_index.get(cat.id, 0)
        if not items:
            return None
        idx = max(0, min(idx, len(items) - 1))
        return items[idx]

    def flash(self, text, seconds=2.8):
        self.message = text
        self.message_until = time.time() + seconds

    # ---------- eventos ----------

    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return

        if self.mode == "browse":
            if event.key in (pygame.K_RIGHT, pygame.K_d):
                self.cat_index = (self.cat_index + 1) % len(self.categories)
                self.current_category().trigger_load()
            elif event.key in (pygame.K_LEFT, pygame.K_a):
                self.cat_index = (self.cat_index - 1) % len(self.categories)
                self.current_category().trigger_load()
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                cat = self.current_category()
                if cat.items:
                    self.item_index[cat.id] = (self.item_index.get(cat.id, 0) + 1) % len(cat.items)
            elif event.key in (pygame.K_UP, pygame.K_w):
                cat = self.current_category()
                if cat.items:
                    self.item_index[cat.id] = (self.item_index.get(cat.id, 0) - 1) % len(cat.items)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if self.selected_item() is not None:
                    self.mode = "detail"
            elif event.key == pygame.K_ESCAPE:
                self.running = False
        elif self.mode == "detail":
            if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                self.mode = "browse"
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                item = self.selected_item()
                if item and item.action:
                    item.action(self, item)

    # ---------- update ----------

    def update(self, dt):
        target = self.cat_index
        self.cat_anim += (target - self.cat_anim) * min(1.0, dt * 11)

        cat = self.current_category()
        target_item = self.item_index.get(cat.id, 0)
        cur = self.item_anim.get(cat.id, target_item)
        cur += (target_item - cur) * min(1.0, dt * 13)
        self.item_anim[cat.id] = cur

        # Partículas
        w, h = self.screen.get_size()
        for p in self.particles:
            p["y"] -= p["speed"] * dt
            if p["y"] < -5:
                p["y"] = h + 5
                p["x"] = random.uniform(0, w)

        if self.message and time.time() > self.message_until:
            self.message = None

    # ---------- draw ----------

    def draw(self):
        surface = self.screen
        w, h = surface.get_size()
        self._draw_background(surface, w, h)
        self._draw_particles(surface, w, h)
        self._draw_clock(surface, w, h)
        self._draw_categories(surface, w, h)
        self._draw_items(surface, w, h)
        if self.mode == "detail":
            self._draw_detail_panel(surface, w, h)
        self._draw_footer(surface, w, h)
        if self.message:
            self._draw_message(surface, w, h)

    def _draw_background(self, surface, w, h):
        if self._wallpaper_surf is not None:
            # Escala o wallpaper para cobrir a tela (cover)
            iw, ih = self._wallpaper_surf.get_size()
            scale = max(w / iw, h / ih)
            nw, nh = int(iw * scale), int(ih * scale)
            scaled = pygame.transform.smoothscale(self._wallpaper_surf, (nw, nh))
            ox, oy = (w - nw) // 2, (h - nh) // 2
            surface.blit(scaled, (ox, oy))
            # Escurece levemente para legibilidade dos ícones
            dim = pygame.Surface((w, h), pygame.SRCALPHA)
            dim.fill((0, 0, 0, 90))
            surface.blit(dim, (0, 0))
        else:
            top = pygame.Color(*theme.BG_TOP)
            bottom = pygame.Color(*theme.BG_BOTTOM)
            for y in range(0, h, 3):
                ratio = y / h
                col = top.lerp(bottom, ratio)
                pygame.draw.rect(surface, col, (0, y, w, 3))

        # Ondas sempre por cima (mais suaves se houver wallpaper)
        t = time.time() - self.t0
        wave_alpha = 50 if self._wallpaper_surf is not None else 85
        for i, (color, speed, amp, yoff) in enumerate([
            (theme.WAVE_COLOR_3, 0.13, 30, 0.80),
            (theme.WAVE_COLOR_2, 0.20, 22, 0.70),
            (theme.WAVE_COLOR_1, 0.28, 15, 0.61),
        ]):
            points = []
            for x in range(0, w + 24, 18):
                y = h * yoff + math.sin(x * 0.0055 + t * speed * 4.2 + i * 1.3) * amp
                points.append((x, y))
            points += [(w, h), (0, h)]
            wave_surf = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.polygon(wave_surf, (*color, wave_alpha), points)
            surface.blit(wave_surf, (0, 0))

    def _draw_particles(self, surface, w, h):
        for p in self.particles:
            s = max(1, int(p["size"]))
            col = (180, 200, 240, p["alpha"])
            pygame.draw.circle(surface, col, (int(p["x"]), int(p["y"])), s)

    def _draw_clock(self, surface, w, h):
        now = datetime.datetime.now()
        txt = now.strftime("%H:%M")
        date_txt = now.strftime("%d/%m/%Y")
        f1 = theme.font(30, bold=True)
        f2 = theme.font(15)
        clock_surf = f1.render(txt, True, theme.TEXT_COLOR)
        date_surf = f2.render(date_txt, True, theme.TEXT_DIM)
        surface.blit(clock_surf, (w - clock_surf.get_width() - 36, 22))
        surface.blit(date_surf, (w - date_surf.get_width() - 36, 56))

        # Nome do sistema com leve destaque
        f_sys = theme.font(16, bold=True)
        sys_surf = f_sys.render(self.system_name, True, theme.ACCENT)
        surface.blit(sys_surf, (36, 28))

        if self.user_display:
            f_user = theme.font(14)
            user_surf = f_user.render(f"● {self.user_display}", True, theme.OK_COLOR)
            surface.blit(user_surf, (36, 52))

    def _draw_categories(self, surface, w, h):
        cy = h * 0.29
        cx_center = w / 2
        gap = theme.ICON_GAP

        for i, cat in enumerate(self.categories):
            offset = i - self.cat_anim
            x = cx_center + offset * gap
            if x < -100 or x > w + 100:
                continue
            dist = abs(offset)
            selected_amt = max(0.0, 1.0 - dist)
            size = theme.ICON_SIZE + (theme.ICON_SIZE_SELECTED - theme.ICON_SIZE) * selected_amt
            alpha = int(255 * max(0.30, 1.0 - dist * 0.42))
            color = theme.ICON_COLOR if selected_amt > 0.5 else theme.ICON_DIM

            # Halo sutil no ícone selecionado
            if selected_amt > 0.75:
                glow_r = int(size * 0.72)
                glow = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
                pygame.draw.circle(glow, (*theme.ACCENT_GLOW, 35), (glow_r, glow_r), glow_r)
                surface.blit(glow, (int(x - glow_r), int(cy - glow_r)))

            draw_icon(surface, cat.icon, (int(x), int(cy)), int(size / 2), color, alpha)

            if selected_amt > 0.82:
                f = theme.font(22, bold=True)
                label = f.render(cat.name, True, theme.TEXT_COLOR)
                surface.blit(label, (int(x - label.get_width() / 2), int(cy + size / 2 + 12)))

    def _draw_items(self, surface, w, h):
        cat = self.current_category()
        base_x = w / 2 + (self.cat_index - self.cat_anim) * theme.ICON_GAP
        base_y = h * 0.29

        if cat.loading:
            f = theme.font(20)
            txt = f.render("Carregando…", True, theme.TEXT_DIM)
            surface.blit(txt, (int(base_x - txt.get_width() / 2), int(base_y + 95)))
            return

        if cat.load_error and not cat.items:
            f = theme.font(17)
            txt = f.render(f"Servidor indisponível: {cat.load_error}", True, theme.ERROR_COLOR)
            surface.blit(txt, (int(base_x - txt.get_width() / 2), int(base_y + 95)))
            return

        if not cat.items:
            f = theme.font(18)
            txt = f.render("(vazio)", True, theme.TEXT_MUTED)
            surface.blit(txt, (int(base_x - txt.get_width() / 2), int(base_y + 95)))
            return

        anim_idx = self.item_anim.get(cat.id, 0)
        gap = theme.ITEM_GAP
        # Ponto de foco fixo: a opção selecionada fica sempre nesta altura
        # (abaixo dos ícones de categoria), e a lista “segue” a seleção.
        focus_y = base_y + 110
        # Margem inferior para não invadir o rodapé
        bottom_limit = h - 70
        top_limit = base_y + 70

        for i, item in enumerate(cat.items):
            offset = i - anim_idx
            y = focus_y + offset * gap

            # Corta itens fora da área útil
            if y < top_limit - gap or y > bottom_limit + gap:
                continue

            dist = abs(offset)
            selected_amt = max(0.0, 1.0 - dist)
            is_selected = dist < 0.08

            # Suaviza opacidade conforme se afasta do foco
            alpha_factor = max(0.25, 1.0 - dist * 0.35)

            size = 17 + (26 - 17) * selected_amt
            if is_selected:
                color = theme.TEXT_COLOR
            else:
                color = theme.TEXT_DIM

            f = theme.font(int(size), bold=is_selected)
            label = f.render(item.name, True, color)
            x = base_x - 8

            # Fundo sutil atrás do item selecionado
            if is_selected:
                pad_x, pad_y = 18, 10
                bg_w = max(label.get_width() + 80, 220)
                bg_h = 36 + (18 if item.subtitle else 0)
                highlight = pygame.Surface((bg_w, bg_h), pygame.SRCALPHA)
                pygame.draw.rect(
                    highlight, (*theme.ACCENT, 28),
                    (0, 0, bg_w, bg_h), border_radius=10
                )
                surface.blit(highlight, (int(x - 36), int(y - bg_h / 2)))

                # Seta de seleção
                pygame.draw.polygon(
                    surface, theme.ACCENT,
                    [(x - 28, y - 8), (x - 28, y + 8), (x - 15, y)]
                )

            surface.blit(label, (int(x), int(y - label.get_height() / 2)))

            if is_selected and item.subtitle:
                f2 = theme.font(13)
                sub = f2.render(item.subtitle, True, theme.TEXT_MUTED)
                surface.blit(sub, (int(x), int(y + label.get_height() / 2 + 1)))

    def _draw_detail_panel(self, surface, w, h):
        item = self.selected_item()
        if not item:
            return
        panel_w, panel_h = 560, 290
        px, py = (w - panel_w) / 2, (h - panel_h) / 2

        # Sombra suave
        shadow = pygame.Surface((panel_w + 20, panel_h + 20), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 90), (10, 10, panel_w, panel_h), border_radius=16)
        surface.blit(shadow, (px - 10, py - 10))

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        pygame.draw.rect(panel, theme.PANEL_BG, (0, 0, panel_w, panel_h), border_radius=16)
        pygame.draw.rect(panel, theme.PANEL_BORDER, (0, 0, panel_w, panel_h), width=2, border_radius=16)
        surface.blit(panel, (px, py))

        draw_icon(surface, item.icon, (int(px + 64), int(py + 64)), 36, theme.ICON_COLOR)

        f_title = theme.font(26, bold=True)
        title = f_title.render(item.name, True, theme.TEXT_COLOR)
        surface.blit(title, (px + 120, py + 32))

        if item.subtitle:
            f_sub = theme.font(16)
            sub = f_sub.render(item.subtitle, True, theme.TEXT_DIM)
            surface.blit(sub, (px + 120, py + 66))

        desc = item.payload.get("description", "")
        price = item.payload.get("price")
        f_desc = theme.font(16)
        y = py + 125
        for line in _wrap_text(desc, f_desc, panel_w - 70):
            surf = f_desc.render(line, True, theme.TEXT_COLOR)
            surface.blit(surf, (px + 35, y))
            y += 24

        if price:
            f_price = theme.font(22, bold=True)
            price_surf = f_price.render(str(price), True, theme.OK_COLOR)
            surface.blit(price_surf, (px + 35, py + panel_h - 52))

        hint = "Enter: confirmar    Esc: voltar" if item.action else "Esc: voltar"
        f_hint = theme.font(14)
        hint_surf = f_hint.render(hint, True, theme.TEXT_MUTED)
        surface.blit(hint_surf, (px + panel_w - hint_surf.get_width() - 24, py + panel_h - 34))

    def _draw_footer(self, surface, w, h):
        f = theme.font(13)
        hint = "← → categorias    ↑ ↓ itens    Enter selecionar    Esc sair"
        txt = f.render(hint, True, theme.TEXT_MUTED)
        surface.blit(txt, (36, h - 38))

    def _draw_message(self, surface, w, h):
        f = theme.font(16, bold=True)
        txt = f.render(self.message, True, theme.TEXT_COLOR)
        pad = 16
        box = pygame.Surface((txt.get_width() + pad * 2, txt.get_height() + pad * 2), pygame.SRCALPHA)
        pygame.draw.rect(box, theme.PANEL_BG, box.get_rect(), border_radius=12)
        pygame.draw.rect(box, theme.PANEL_BORDER, box.get_rect(), width=2, border_radius=12)
        box.blit(txt, (pad, pad))
        surface.blit(box, (w / 2 - box.get_width() / 2, h - 105))


def _wrap_text(text, font_obj, max_width):
    words = text.split()
    lines = []
    cur = ""
    for word in words:
        trial = f"{cur} {word}".strip()
        if font_obj.size(trial)[0] > max_width and cur:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines
