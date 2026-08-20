"""Cliente da Loja Online com autenticação, compra e download."""
import io
import os
import zipfile
from pathlib import Path

import requests

from . import mock_data
from . import session as sess

VALID_ICONS = {"game", "music", "video", "photo", "generic", "store"}

ROOT = Path(__file__).resolve().parent.parent
GAMES_DIR = ROOT / "games"
WALLPAPERS_DIR = ROOT / "wallpapers"


class StoreError(Exception):
    pass


class StoreClient:
    def __init__(self, base_url, timeout=5, token=None):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.token = token or sess.get_token()

    def _headers(self):
        h = {}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
            h["X-Token"] = self.token
        return h

    def health(self):
        try:
            r = requests.get(f"{self.base_url}/api/health", timeout=self.timeout)
            return r.ok
        except requests.RequestException:
            return False

    def get_items_raw(self):
        try:
            r = requests.get(
                f"{self.base_url}/api/store/items",
                timeout=self.timeout,
                headers=self._headers(),
            )
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            raise StoreError(str(exc)) from exc

    def get_item_raw(self, item_id):
        try:
            r = requests.get(
                f"{self.base_url}/api/store/items/{item_id}",
                timeout=self.timeout,
                headers=self._headers(),
            )
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            raise StoreError(str(exc)) from exc

    def login(self, username, password):
        try:
            r = requests.post(
                f"{self.base_url}/api/auth/login",
                json={"username": username, "password": password},
                timeout=self.timeout,
            )
            data = r.json()
            if not r.ok or not data.get("success"):
                raise StoreError(data.get("error", "Falha no login"))
            self.token = data["token"]
            sess.set_logged_in(data["token"], data["user"])
            return data
        except requests.RequestException as exc:
            raise StoreError(str(exc)) from exc

    def register(self, username, password, display_name=None):
        try:
            r = requests.post(
                f"{self.base_url}/api/auth/register",
                json={
                    "username": username,
                    "password": password,
                    "display_name": display_name or username,
                },
                timeout=self.timeout,
            )
            data = r.json()
            if not r.ok or not data.get("success"):
                raise StoreError(data.get("error", "Falha no registro"))
            self.token = data["token"]
            sess.set_logged_in(data["token"], data["user"])
            return data
        except requests.RequestException as exc:
            raise StoreError(str(exc)) from exc

    def logout(self):
        self.token = None
        sess.clear_session()

    def purchase(self, item_id, user="convidado"):
        try:
            r = requests.post(
                f"{self.base_url}/api/store/purchase",
                json={"item_id": item_id, "user": user},
                timeout=self.timeout,
                headers=self._headers(),
            )
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            raise StoreError(str(exc)) from exc

    def download_item_file(self, item_id):
        """Baixa o arquivo associado ao item (ZIP de jogo ou imagem de wallpaper).

        Retorna bytes do conteúdo ou None se não houver arquivo.
        """
        try:
            r = requests.get(
                f"{self.base_url}/api/store/items/{item_id}/download",
                timeout=max(self.timeout, 30),
                headers=self._headers(),
            )
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.content
        except requests.RequestException as exc:
            raise StoreError(str(exc)) from exc

    def install_game(self, item_id, item_name=None):
        """Baixa o ZIP do jogo, extrai automaticamente em games/<slug>/ e retorna o caminho."""
        content = self.download_item_file(item_id)
        if not content:
            raise StoreError("Este item não possui arquivo para download.")

        # Se o conteúdo for uma imagem (wallpaper), não é jogo
        if content[:4] == b"\x89PNG" or content[:3] == b"\xff\xd8\xff" or content[:4] == b"GIF8":
            raise StoreError("O arquivo baixado é uma imagem, não um jogo ZIP.")

        import json as _json
        import shutil

        slug = f"store_{item_id}"
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                members = [m for m in zf.namelist() if m and not m.endswith("/")]
                if not members:
                    raise StoreError("ZIP vazio.")

                # id preferencial a partir do game.json
                for name in members:
                    norm = name.replace("\\", "/")
                    if norm.endswith("game.json"):
                        meta = _json.loads(zf.read(name).decode("utf-8"))
                        if meta.get("id"):
                            slug = str(meta["id"]).strip().replace(" ", "_")
                        break

                dest = GAMES_DIR / slug
                if dest.exists():
                    shutil.rmtree(dest)
                dest.mkdir(parents=True, exist_ok=True)

                # Remove um único diretório raiz comum (ex.: snake_pkg/)
                top_dirs = set()
                for m in zf.namelist():
                    parts = m.replace("\\", "/").split("/")
                    if parts and parts[0]:
                        top_dirs.add(parts[0])
                strip_prefix = None
                if len(top_dirs) == 1:
                    only = next(iter(top_dirs))
                    if any("/" in m.replace("\\", "/") for m in members):
                        strip_prefix = only + "/"

                extracted = 0
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    name = info.filename.replace("\\", "/")
                    if strip_prefix and name.startswith(strip_prefix):
                        name = name[len(strip_prefix):]
                    if not name or name.endswith("/"):
                        continue
                    if ".." in name.split("/"):
                        continue
                    target = dest / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info) as src, open(target, "wb") as out:
                        out.write(src.read())
                    extracted += 1

                if extracted == 0:
                    raise StoreError("Nenhum arquivo pôde ser extraído do ZIP.")

                gj = dest / "game.json"
                if not gj.exists():
                    gj.write_text(
                        _json.dumps({
                            "id": slug,
                            "name": item_name or slug,
                            "description": "Instalado pela Loja Online.",
                            "icon": "game",
                            "entry": "main.py",
                        }, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
        except zipfile.BadZipFile as exc:
            raise StoreError("Arquivo ZIP inválido.") from exc

        return str(dest)

    def install_wallpaper(self, item_id, filename_hint=None):
        """Baixa a imagem do wallpaper e salva em wallpapers/."""
        content = self.download_item_file(item_id)
        if not content:
            raise StoreError("Este item não possui arquivo de imagem.")

        WALLPAPERS_DIR.mkdir(parents=True, exist_ok=True)
        # Detecta extensão pelo magic bytes
        ext = ".png"
        if content[:3] == b"\xff\xd8\xff":
            ext = ".jpg"
        elif content[:4] == b"\x89PNG":
            ext = ".png"
        elif content[:4] == b"GIF8":
            ext = ".gif"
        elif content[:2] == b"BM":
            ext = ".bmp"

        path = WALLPAPERS_DIR / f"wp_{item_id}{ext}"
        with open(path, "wb") as f:
            f.write(content)
        return str(path)

    def load_items_as_xmb_items(self, on_action=None):
        """Retorna list[xmb.engine.Item] para a categoria da Loja.

        on_action(engine, item, data) é chamado ao confirmar um item
        (compra + download se aplicável). Se None, usa comportamento padrão.
        """
        from xmb.engine import Item

        try:
            raw_items = self.get_items_raw()
            offline = False
        except StoreError:
            raw_items = mock_data.MOCK_ITEMS
            offline = True

        items = []
        for data in raw_items:
            icon = data.get("icon", "store")
            if icon not in VALID_ICONS:
                icon = "store"
            subtitle = data.get("category", "")
            if offline:
                subtitle = f"{subtitle} · offline"
            elif data.get("has_file"):
                subtitle = f"{subtitle} · baixável"

            def make_action(item_data=data):
                def action(engine, item):
                    if on_action:
                        on_action(engine, item, item_data)
                        return
                    # fallback mínimo
                    if offline:
                        engine.flash(f"Sem conexão — não é possível adquirir '{item_data['name']}'.")
                        return
                    try:
                        result = self.purchase(item_data["id"])
                        engine.flash(result.get("message", "Adquirido!"))
                    except StoreError as exc:
                        engine.flash(f"Falha: {exc}")

                return action

            items.append(
                Item(
                    item_id=data["id"],
                    name=data["name"],
                    subtitle=subtitle,
                    icon=icon,
                    payload={
                        "description": data.get("description", ""),
                        "price": data.get("price"),
                        "category": data.get("category"),
                        "has_file": data.get("has_file", False),
                        "raw": data,
                    },
                    action=make_action(),
                )
            )
        return items
