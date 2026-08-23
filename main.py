"""XMB-PY 3.1 — sistema com interface estilo XMB.

Recursos:
  - Login / registro na categoria Usuários
  - Loja Online em tela cheia (XMB Store)
  - Download e extração automática de jogos
  - Wallpapers personalizados
  - Atualizações automáticas (compara versões dos ZIPs no servidor)
  - Menu de pausa nos jogos (Esc)
  - Configurações de vídeo, som e rede

Executar:
    pip install -r requirements.txt
    python main.py
"""
import json
import os
import sys
from pathlib import Path

import pygame

from xmb import theme
from xmb.engine import XMBEngine, Category, Item
from xmb.dialog import text_input_dialog, confirm_dialog, choice_dialog
from store.client import StoreClient, StoreError
from store import session as sess
from games.registry import discover_games, uninstall_game
from xmb.store_ui import StoreUI
from store.updater import Updater, get_local_version, parse_version
from xmb.boot import run_first_boot, run_startup
from xmb import audio as xmb_audio

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
WALLPAPERS_DIR = ROOT / "wallpapers"


def load_config():
    default = {
        "system_name": "XMB-PY",
        "store_server_url": "http://127.0.0.1:5000",
        "store_request_timeout": 5,
        "fullscreen": False,
        "wallpaper": None,
        "auto_update": True,
        "update_source": "auto",
        "github_repo": "",
        "github_token": "",
        "volume": 80,
        "first_boot_done": False,
    }
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                default.update(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass
    return default


def save_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def apply_fullscreen(engine, fullscreen):
    engine.fullscreen = bool(fullscreen)
    flags = pygame.FULLSCREEN if engine.fullscreen else pygame.RESIZABLE
    screen = pygame.display.set_mode((theme.SCREEN_W, theme.SCREEN_H), flags)
    engine.screen = screen


def apply_volume(percent):
    percent = max(0, min(100, int(percent)))
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        pygame.mixer.music.set_volume(percent / 100.0)
    except pygame.error:
        pass
    try:
        xmb_audio.set_volume(percent)
    except Exception:
        pass
    return percent


def make_game_action(run_func, game_id, game_name):
    """Ao confirmar um jogo: menu Jogar / Desinstalar."""

    def action(engine, item):
        engine.mode = "browse"
        clock = pygame.time.Clock()
        choice = choice_dialog(
            engine.screen, clock,
            game_name,
            [
                ("play", "Jogar"),
                ("uninstall", "Desinstalar"),
                ("cancel", "Cancelar"),
            ],
        )
        if choice == "play":
            quit_requested = run_func(engine.screen, clock)
            if quit_requested:
                engine.running = False
        elif choice == "uninstall":
            ok = confirm_dialog(
                engine.screen, clock,
                "Desinstalar",
                f"Remover '{game_name}' deste aparelho?",
                yes_label="Desinstalar", no_label="Cancelar",
            )
            if ok:
                if uninstall_game(game_id):
                    game_cat = next(c for c in engine.categories if c.id == "game")
                    game_cat.items = build_game_items()
                    engine.flash(f"'{game_name}' desinstalado.")
                else:
                    engine.flash("Não foi possível desinstalar o jogo.")
    return action


def build_game_items():
    games = discover_games()
    if not games:
        return [
            Item(
                "none", "Nenhum jogo instalado", "", "game",
                {"description": "Baixe jogos na Loja Online ou adicione pastas em games/."},
            ),
        ]
    items = []
    for g in games:
        items.append(
            Item(
                g["id"], g["name"], "Instalado · Enter para opções", g.get("icon", "game"),
                {"description": g["description"] + "\n\nEnter: Jogar ou Desinstalar."},
                action=make_game_action(g["run"], g["id"], g["name"]),
            )
        )
    return items


def list_local_wallpapers():
    WALLPAPERS_DIR.mkdir(parents=True, exist_ok=True)
    result = []
    for p in sorted(WALLPAPERS_DIR.iterdir()):
        if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp", ".gif"}:
            result.append(p)
    return result


def build_categories(config, store_client, engine_ref):
    """engine_ref é uma lista de 1 elemento [engine] preenchida após criação."""

    def refresh_users_category(engine):
        """Reconstrói os itens da categoria Usuários conforme o estado da sessão."""
        user = sess.get_user()
        cat = next(c for c in engine.categories if c.id == "users")
        if user:
            cat.items = [
                Item(
                    "profile", user.get("display_name") or user.get("username"),
                    "Conectado", "user",
                    {"description": f"Logado como {user.get('username')}."},
                ),
                Item(
                    "logout", "Sair da conta", "", "power",
                    {"description": "Encerra a sessão local."},
                    action=do_logout,
                ),
            ]
            engine.user_display = user.get("display_name") or user.get("username")
        else:
            cat.items = [
                Item(
                    "login", "Entrar", "Fazer login na conta", "user",
                    {"description": "Entre com seu usuário e senha da loja."},
                    action=do_login,
                ),
                Item(
                    "register", "Criar conta", "Registrar novo usuário", "user",
                    {"description": "Crie uma conta no servidor da loja."},
                    action=do_register,
                ),
                Item(
                    "guest", "Continuar como convidado", "Sessão local", "user",
                    {"description": "Use o sistema sem conta (compras não persistidas)."},
                ),
            ]
            engine.user_display = None

    def do_login(engine, item):
        clock = pygame.time.Clock()
        result = text_input_dialog(
            engine.screen, clock, "Entrar na conta",
            [
                {"key": "username", "label": "Usuário"},
                {"key": "password", "label": "Senha", "password": True},
            ],
            submit_label="Entrar",
        )
        if not result:
            return
        try:
            data = store_client.login(result["username"], result["password"])
            refresh_users_category(engine)
            engine.flash(f"Bem-vindo, {data['user'].get('display_name', result['username'])}!")
            # Recarrega a loja com o token
            store_cat = next(c for c in engine.categories if c.id == "store")
            store_cat.loaded_once = False
            store_cat.trigger_load()
        except StoreError as exc:
            engine.flash(f"Login falhou: {exc}")

    def do_register(engine, item):
        clock = pygame.time.Clock()
        result = text_input_dialog(
            engine.screen, clock, "Criar conta",
            [
                {"key": "username", "label": "Usuário"},
                {"key": "display_name", "label": "Nome de exibição"},
                {"key": "password", "label": "Senha", "password": True},
            ],
            submit_label="Registrar",
        )
        if not result:
            return
        try:
            data = store_client.register(
                result["username"], result["password"],
                display_name=result.get("display_name") or result["username"],
            )
            refresh_users_category(engine)
            engine.flash(f"Conta criada! Olá, {data['user'].get('display_name')}!")
            store_cat = next(c for c in engine.categories if c.id == "store")
            store_cat.loaded_once = False
            store_cat.trigger_load()
        except StoreError as exc:
            engine.flash(f"Registro falhou: {exc}")

    def do_logout(engine, item):
        store_client.logout()
        refresh_users_category(engine)
        engine.flash("Sessão encerrada.")
        store_cat = next(c for c in engine.categories if c.id == "store")
        store_cat.loaded_once = False
        store_cat.trigger_load()

    def on_store_action(engine, item, data):
        """Compra + download automático com extração de jogos e wallpapers."""
        cat = (data.get("category") or "").lower()
        icon = (data.get("icon") or "").lower()
        is_wallpaper = cat in ("tema", "wallpaper", "foto", "photo") or icon == "photo"
        is_game = cat in ("jogo", "game") or icon == "game"
        has_file = bool(data.get("has_file"))
        name = data.get("name", item.name)
        item_id = data["id"]

        try:
            user = sess.get_user()
            result = store_client.purchase(
                item_id, user=(user or {}).get("username", "convidado")
            )
            msg = result.get("message", f"'{name}' adquirido!")

            if not has_file:
                engine.flash(msg)
                return

            # Baixa o arquivo uma vez e decide pelo conteúdo
            engine.flash("Baixando…")
            pygame.display.flip()
            content = store_client.download_item_file(item_id)
            if not content:
                engine.flash(f"{msg} (sem arquivo para baixar)")
                return

            is_image = (
                content[:4] == b"\x89PNG"
                or content[:3] == b"\xff\xd8\xff"
                or content[:4] == b"GIF8"
                or content[:2] == b"BM"
            )
            is_zip = content[:2] == b"PK"

            if is_zip or (is_game and not is_image):
                engine.flash("Extraindo e instalando jogo…")
                pygame.display.flip()
                dest = store_client.install_game(item_id, name)
                game_cat = next(c for c in engine.categories if c.id == "game")
                game_cat.items = build_game_items()
                engine.flash(f"Jogo instalado: {Path(dest).name}")
            elif is_image or is_wallpaper:
                engine.flash("Salvando wallpaper…")
                pygame.display.flip()
                path = store_client.install_wallpaper(item_id)
                clock = pygame.time.Clock()
                apply = confirm_dialog(
                    engine.screen, clock,
                    "Wallpaper baixado",
                    f"'{name}' salvo. Deseja aplicar agora?",
                    yes_label="Aplicar", no_label="Depois",
                )
                if apply:
                    engine.set_wallpaper(path)
                    config = load_config()
                    config["wallpaper"] = path
                    save_config(config)
                    _refresh_photo_category(engine)
                    engine.flash(f"Wallpaper '{name}' aplicado!")
                else:
                    _refresh_photo_category(engine)
                    engine.flash(f"{msg} Salvo em wallpapers/.")
            else:
                engine.flash(msg)
        except StoreError as exc:
            engine.flash(f"Falha: {exc}")

    def _refresh_photo_category(engine):
        cat = next(c for c in engine.categories if c.id == "photo")
        cat.items = _build_photo_items(engine)

    def _build_photo_items(engine):
        items = []
        # Opção: restaurar padrão
        def clear_wp(eng, it):
            eng.set_wallpaper(None)
            cfg = load_config()
            cfg["wallpaper"] = None
            save_config(cfg)
            eng.flash("Fundo padrão restaurado.")

        items.append(
            Item(
                "default_bg", "Fundo padrão (ondas)", "Sistema", "photo",
                {"description": "Restaura o gradiente e ondas originais da XMB."},
                action=clear_wp,
            )
        )
        for p in list_local_wallpapers():
            def make_apply(path=str(p)):
                def apply(eng, it):
                    eng.set_wallpaper(path)
                    cfg = load_config()
                    cfg["wallpaper"] = path
                    save_config(cfg)
                    eng.flash(f"Wallpaper aplicado: {Path(path).name}")
                return apply

            items.append(
                Item(
                    p.stem, p.stem, "Local", "photo",
                    {"description": f"Arquivo: {p.name}. Enter para aplicar como fundo."},
                    action=make_apply(),
                )
            )
        if len(items) == 1:
            items.append(
                Item(
                    "hint", "Baixe wallpapers na Loja", "", "store",
                    {"description": "Na Loja Online, adquira itens da categoria Tema/Foto para desbloquear novos fundos."},
                )
            )
        return items

    def enter_store(engine, item):
        """Abre a interface completa da XMB Store."""
        engine.mode = "browse"

        def on_game_installed(dest):
            game_cat = next(c for c in engine.categories if c.id == "game")
            game_cat.items = build_game_items()

        def on_wp_installed(path):
            engine.set_wallpaper(path)
            cfg = load_config()
            cfg["wallpaper"] = path
            save_config(cfg)
            _refresh_photo_category(engine)

        clock = pygame.time.Clock()
        ui = StoreUI(
            engine.screen, clock, store_client,
            on_install_game=on_game_installed,
            on_install_wallpaper=on_wp_installed,
        )
        quit_app = ui.run()
        if quit_app:
            engine.running = False

    def check_for_updates(engine, item):
        """Verifica no servidor se há ZIP de versão mais nova e oferece instalar."""
        updater = Updater(
            config.get("store_server_url", ""),
            timeout=config.get("store_request_timeout", 12),
            source=config.get("update_source", "auto"),
            github_repo=config.get("github_repo", ""),
            github_token=config.get("github_token", ""),
        )
        engine.flash("Verificando atualizações…")
        pygame.display.flip()
        try:
            latest = updater.latest_newer_than_local()
        except Exception as exc:
            engine.flash(f"Falha ao verificar: {exc}")
            return

        local = get_local_version()
        if not latest:
            engine.flash(f"Sistema atualizado (v{local}).")
            return

        clock = pygame.time.Clock()
        ok = confirm_dialog(
            engine.screen, clock,
            "Atualização disponível",
            f"Versão local: {local}  →  Nova: {latest.version}. Deseja baixar e instalar?",
            yes_label="Atualizar", no_label="Depois",
        )
        if not ok:
            engine.flash("Atualização adiada.")
            return

        try:
            engine.flash(f"Baixando {latest.filename}…")
            pygame.display.flip()
            zip_path = updater.download(latest)
            engine.flash("Aplicando atualização…")
            pygame.display.flip()
            written = updater.apply(zip_path, latest.version)
            engine.flash(
                f"Atualizado para v{latest.version} ({len(written)} arquivos). Reinicie o XMB-PY."
            )
        except Exception as exc:
            engine.flash(f"Falha na atualização: {exc}")

    def _refresh_settings_category(engine):
        cat = next(c for c in engine.categories if c.id == "settings")
        cat.items = _build_settings_items()

    def _build_settings_items():
        cfg = load_config()
        fs_label = "Tela cheia" if cfg.get("fullscreen") else "Janela"
        vol = int(cfg.get("volume", 80))
        url = cfg.get("store_server_url", "")
        auto = "Ativado" if cfg.get("auto_update", True) else "Desativado"
        src = cfg.get("update_source", "auto")
        return [
            Item(
                "display", "Vídeo", fs_label, "settings",
                {"description": f"Modo de exibição atual: {fs_label}. Resolução {theme.SCREEN_W}×{theme.SCREEN_H}. F11 também alterna tela cheia."},
                action=do_video,
            ),
            Item(
                "sound", "Som", f"Volume {vol}%", "settings",
                {"description": "Volume geral do sistema (0 a 100)."},
                action=do_sound,
            ),
            Item(
                "network", "Rede", url.replace("https://", "").replace("http://", "")[:40], "network",
                {"description": f"Servidor da loja: {url}\nTempo limite: {cfg.get('store_request_timeout', 12)} s."},
                action=do_network,
            ),
            Item(
                "auto_update", "Atualização automática", auto, "settings",
                {"description": "Ao ligar o sistema, verifica se há uma versão mais nova."},
                action=do_auto_update,
            ),
            Item(
                "update_source", "Fonte de atualização", src, "settings",
                {"description": "github = releases do repositório; store = API da loja; auto = tenta os dois."},
                action=do_update_source,
            ),
            Item(
                "update", "Verificar atualizações", f"Versão {get_local_version()}", "settings",
                {"description": "Compara a versão local com os ZIPs publicados (ex.: 2.0.zip vs 4.0.zip) e instala a mais nova."},
                action=check_for_updates,
            ),
        ]

    def do_video(engine, item):
        cfg = load_config()
        clock = pygame.time.Clock()
        choice = choice_dialog(
            engine.screen, clock, "Vídeo",
            [
                ("full", "Tela cheia"),
                ("window", "Janela"),
                ("cancel", "Cancelar"),
            ],
        )
        if choice not in ("full", "window"):
            return
        fs = choice == "full"
        cfg["fullscreen"] = fs
        save_config(cfg)
        apply_fullscreen(engine, fs)
        _refresh_settings_category(engine)
        engine.flash("Tela cheia ativada." if fs else "Modo janela.")

    def do_sound(engine, item):
        cfg = load_config()
        clock = pygame.time.Clock()
        choice = choice_dialog(
            engine.screen, clock, "Volume",
            [
                ("0", "Mudo (0%)"),
                ("25", "Baixo (25%)"),
                ("50", "Médio (50%)"),
                ("75", "Alto (75%)"),
                ("100", "Máximo (100%)"),
                ("custom", "Personalizar…"),
                ("cancel", "Cancelar"),
            ],
        )
        if not choice or choice == "cancel":
            return
        if choice == "custom":
            result = text_input_dialog(
                engine.screen, clock, "Volume (0–100)",
                [{"key": "volume", "label": "Volume", "value": str(int(cfg.get("volume", 80)))}],
                submit_label="Aplicar",
            )
            if not result:
                return
            try:
                vol = int(result["volume"])
            except ValueError:
                engine.flash("Informe um número entre 0 e 100.")
                return
        else:
            vol = int(choice)
        vol = apply_volume(vol)
        cfg["volume"] = vol
        save_config(cfg)
        _refresh_settings_category(engine)
        engine.flash(f"Volume definido para {vol}%.")

    def do_network(engine, item):
        cfg = load_config()
        clock = pygame.time.Clock()
        choice = choice_dialog(
            engine.screen, clock, "Rede",
            [
                ("test", "Testar conexão"),
                ("url", "Alterar URL da loja"),
                ("timeout", "Tempo limite"),
                ("cancel", "Cancelar"),
            ],
        )
        if choice == "test":
            engine.flash(
                "Servidor online ✓" if store_client.health() else "Servidor offline ✗"
            )
        elif choice == "url":
            result = text_input_dialog(
                engine.screen, clock, "URL da loja",
                [{"key": "url", "label": "Endereço", "value": cfg.get("store_server_url", "")}],
                submit_label="Salvar",
            )
            if not result:
                return
            url = result["url"].strip().rstrip("/")
            if not url.startswith("http"):
                engine.flash("A URL deve começar com http:// ou https://")
                return
            cfg["store_server_url"] = url
            save_config(cfg)
            store_client.base_url = url
            _refresh_settings_category(engine)
            engine.flash(f"Loja apontando para {url}")
        elif choice == "timeout":
            result = text_input_dialog(
                engine.screen, clock, "Tempo limite (segundos)",
                [{"key": "timeout", "label": "Segundos", "value": str(cfg.get("store_request_timeout", 12))}],
                submit_label="Salvar",
            )
            if not result:
                return
            try:
                t = max(1, min(60, int(result["timeout"])))
            except ValueError:
                engine.flash("Informe um número válido.")
                return
            cfg["store_request_timeout"] = t
            save_config(cfg)
            store_client.timeout = t
            _refresh_settings_category(engine)
            engine.flash(f"Tempo limite: {t} s.")

    def do_auto_update(engine, item):
        cfg = load_config()
        cfg["auto_update"] = not cfg.get("auto_update", True)
        save_config(cfg)
        _refresh_settings_category(engine)
        engine.flash(
            "Atualização automática ativada." if cfg["auto_update"] else "Atualização automática desativada."
        )

    def do_update_source(engine, item):
        clock = pygame.time.Clock()
        choice = choice_dialog(
            engine.screen, clock, "Fonte de atualização",
            [
                ("github", "GitHub Releases"),
                ("store", "Servidor da loja"),
                ("auto", "Automático (GitHub + loja)"),
                ("cancel", "Cancelar"),
            ],
        )
        if not choice or choice == "cancel":
            return
        cfg = load_config()
        cfg["update_source"] = choice
        if choice in ("github", "auto"):
            result = text_input_dialog(
                engine.screen, clock, "Repositório GitHub",
                [{"key": "repo", "label": "usuario/repositorio",
                  "value": cfg.get("github_repo", "")}],
                submit_label="Salvar",
            )
            if result:
                cfg["github_repo"] = result["repo"].strip()
        save_config(cfg)
        _refresh_settings_category(engine)
        engine.flash(f"Fonte de atualização: {choice}.")

    def open_placeholder(engine, item):
        engine.flash(f"'{item.name}' — em breve.")

    # Itens iniciais de usuários (serão atualizados após engine existir)
    user = sess.get_user()
    if user:
        user_items = [
            Item("profile", user.get("display_name") or user.get("username"),
                 "Conectado", "user",
                 {"description": f"Logado como {user.get('username')}."}),
            Item("logout", "Sair da conta", "", "power",
                 {"description": "Encerra a sessão local."}, action=do_logout),
        ]
    else:
        user_items = [
            Item("login", "Entrar", "Fazer login na conta", "user",
                 {"description": "Entre com seu usuário e senha da loja."}, action=do_login),
            Item("register", "Criar conta", "Registrar novo usuário", "user",
                 {"description": "Crie uma conta no servidor da loja."}, action=do_register),
            Item("guest", "Continuar como convidado", "Sessão local", "user",
                 {"description": "Use o sistema sem conta (compras não persistidas)."}),
        ]

    categories = [
        Category("users", "Usuários", "user", items=user_items),
        Category(
            "settings", "Configurações", "settings",
            items=_build_settings_items(),
        ),
        Category(
            "photo", "Fotos", "photo",
            items=[],  # preenchido abaixo
        ),
        Category(
            "music", "Música", "music",
            items=[
                Item("playlist1", "Minhas Faixas", "12 músicas", "music",
                     {"description": "Biblioteca de música local."}, action=open_placeholder),
            ],
        ),
        Category(
            "video", "Vídeo", "video",
            items=[
                Item("clips", "Meus Vídeos", "5 vídeos", "video",
                     {"description": "Biblioteca de vídeos local."}, action=open_placeholder),
            ],
        ),
        Category("game", "Jogos", "game", items=build_game_items()),
        Category(
            "store", "Loja Online", "store",
            items=[
                Item(
                    "enter_store", "Entrar na Store", "XMB Store",
                    "store",
                    {"description": "Abre a XMB Store em tela cheia — navegue, compre e baixe jogos e temas."},
                    action=enter_store,
                ),
                Item(
                    "store_web", "Abrir no navegador", "Site da loja",
                    "network",
                    {"description": f"Acesse a loja pelo navegador: {config.get('store_server_url', '')}"},
                    action=lambda eng, it: eng.flash(
                        f"Abra no navegador: {config.get('store_server_url', '')}"
                    ),
                ),
            ],
        ),
        Category(
            "network", "Rede", "network",
            items=[
                Item(
                    "status", "Status da Conexão", "", "network",
                    {"description": "Verifique a conectividade com o servidor da loja."},
                    action=lambda engine, item: engine.flash(
                        "Servidor online ✓" if store_client.health() else "Servidor offline ✗"
                    ),
                ),
            ],
        ),
        Category(
            "friends", "Amigos", "friends",
            items=[
                Item("none", "Nenhum amigo online", "", "friends",
                     {"description": "Lista de amigos (recurso futuro)."}),
            ],
        ),
        Category(
            "power", "Desligar", "power",
            items=[
                Item(
                    "exit", "Sair do Sistema", "", "power",
                    {"description": "Encerra o XMB-PY."},
                    action=lambda engine, item: setattr(engine, "running", False),
                ),
            ],
        ),
    ]

    # Preenche fotos (wallpapers locais)
    photo_cat = next(c for c in categories if c.id == "photo")
    # engine ainda não existe — montamos itens sem depender dele
    photo_items = [
        Item(
            "default_bg", "Fundo padrão (ondas)", "Sistema", "photo",
            {"description": "Restaura o gradiente e ondas originais da XMB."},
            action=lambda eng, it: (
                eng.set_wallpaper(None),
                save_config({**load_config(), "wallpaper": None}),
                eng.flash("Fundo padrão restaurado."),
            ),
        )
    ]
    for p in list_local_wallpapers():
        def make_apply(path=str(p)):
            def apply(eng, it):
                eng.set_wallpaper(path)
                cfg = load_config()
                cfg["wallpaper"] = path
                save_config(cfg)
                eng.flash(f"Wallpaper aplicado: {Path(path).name}")
            return apply
        photo_items.append(
            Item(
                p.stem, p.stem, "Local", "photo",
                {"description": f"Arquivo: {p.name}. Enter para aplicar como fundo."},
                action=make_apply(),
            )
        )
    if len(photo_items) == 1:
        photo_items.append(
            Item(
                "hint", "Baixe wallpapers na Loja", "", "store",
                {"description": "Na Loja Online, adquira itens da categoria Tema para novos fundos."},
            )
        )
    photo_cat.items = photo_items

    return categories


def main():
    config = load_config()

    pygame.init()
    pygame.joystick.init()
    for i in range(pygame.joystick.get_count()):
        try:
            pygame.joystick.Joystick(i).init()
        except pygame.error:
            pass

    pygame.display.set_caption(config.get("system_name", "XMB-PY"))

    flags = pygame.FULLSCREEN if config.get("fullscreen") else pygame.RESIZABLE
    screen = pygame.display.set_mode((theme.SCREEN_W, theme.SCREEN_H), flags)
    clock = pygame.time.Clock()

    # Áudio
    xmb_audio.init(config.get("volume", 80))
    apply_volume(config.get("volume", 80))

    # Tela de inicialização
    system_name = config.get("system_name", "XMB-PY")
    if not config.get("first_boot_done", False):
        if run_first_boot(screen, clock, system_name=system_name):
            pygame.quit()
            sys.exit(0)
        config["first_boot_done"] = True
        save_config(config)
    else:
        if run_startup(screen, clock, system_name=system_name):
            pygame.quit()
            sys.exit(0)

    store_client = StoreClient(
        config["store_server_url"],
        timeout=config.get("store_request_timeout", 5),
    )

    categories = build_categories(config, store_client, engine_ref=[])
    wallpaper = config.get("wallpaper")
    if wallpaper and not Path(wallpaper).is_file():
        wallpaper = None

    engine = XMBEngine(
        screen, categories,
        system_name=config.get("system_name", "XMB-PY"),
        wallpaper_path=wallpaper,
    )

    user = sess.get_user()
    if user:
        engine.user_display = user.get("display_name") or user.get("username")

    # Verificação silenciosa de atualização na inicialização
    if config.get("auto_update", True):
        try:
            updater = Updater(
                config.get("store_server_url", ""),
                timeout=config.get("store_request_timeout", 12),
                source=config.get("update_source", "auto"),
                github_repo=config.get("github_repo", ""),
                github_token=config.get("github_token", ""),
            )
            latest = updater.latest_newer_than_local()
            if latest:
                engine.flash(
                    f"Nova versão disponível: v{latest.version} (atual: v{get_local_version()}). "
                    "Vá em Configurações → Atualizações."
                )
        except Exception:
            pass

    fullscreen = config.get("fullscreen", False)

    while engine.running:
        dt = clock.tick(theme.FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                engine.running = False
            elif event.type == pygame.VIDEORESIZE and not fullscreen:
                screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
                engine.screen = screen
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                fullscreen = not fullscreen
                if fullscreen:
                    screen = pygame.display.set_mode(
                        (theme.SCREEN_W, theme.SCREEN_H), pygame.FULLSCREEN
                    )
                else:
                    screen = pygame.display.set_mode(
                        (theme.SCREEN_W, theme.SCREEN_H), pygame.RESIZABLE
                    )
                engine.screen = screen
            else:
                engine.handle_event(event)

        engine.update(dt)
        engine.draw()
        pygame.display.flip()

    xmb_audio.play("shutdown")
    pygame.time.wait(400)
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
