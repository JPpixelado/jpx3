"""XMB-PY 3.1 — sistema com interface estilo XMB (PS3).

Recursos:
  - Login / registro na categoria Usuários
  - Loja Online em tela cheia (visual PS Store)
  - Download e extração automática de jogos
  - Wallpapers personalizados
  - Atualizações automáticas (compara versões dos ZIPs no servidor)
  - Menu de pausa nos jogos (Esc)

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
from xmb.dialog import text_input_dialog, confirm_dialog
from store.client import StoreClient, StoreError
from store import session as sess
from games.registry import discover_games
from xmb.store_ui import StoreUI
from store.updater import Updater, get_local_version, parse_version

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


def make_launch_action(run_func):
    def action(engine, item):
        engine.mode = "browse"
        clock = pygame.time.Clock()
        quit_requested = run_func(engine.screen, clock)
        if quit_requested:
            engine.running = False
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
                g["id"], g["name"], "Instalado", g.get("icon", "game"),
                {"description": g["description"]},
                action=make_launch_action(g["run"]),
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
        """Abre a interface completa da loja (estilo PS Store)."""
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
            config["store_server_url"],
            timeout=config.get("store_request_timeout", 12),
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

    def open_settings(engine, item):
        engine.flash(f"'{item.name}' — em construção nesta demo.")

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
            items=[
                Item("display", "Vídeo", "Resolução e tela cheia", "settings",
                     {"description": "Ajustes de exibição do sistema."}, action=open_settings),
                Item("sound", "Som", "Volume geral", "settings",
                     {"description": "Ajustes de áudio do sistema."}, action=open_settings),
                Item("network", "Rede", "Configuração de conexão", "network",
                     {"description": "Configurações de rede e servidor da loja."}, action=open_settings),
                Item("update", "Atualizações", f"Versão {get_local_version()}", "settings",
                     {"description": "Verifica no servidor se há uma versão mais nova do sistema (compara ZIPs como 2.0.zip e 4.0.zip)."},
                     action=check_for_updates),
            ],
        ),
        Category(
            "photo", "Fotos", "photo",
            items=[],  # preenchido abaixo
        ),
        Category(
            "music", "Música", "music",
            items=[
                Item("playlist1", "Minhas Faixas", "12 músicas", "music",
                     {"description": "Biblioteca de música local."}, action=open_settings),
            ],
        ),
        Category(
            "video", "Vídeo", "video",
            items=[
                Item("clips", "Meus Vídeos", "5 vídeos", "video",
                     {"description": "Biblioteca de vídeos local."}, action=open_settings),
            ],
        ),
        Category("game", "Jogos", "game", items=build_game_items()),
        Category(
            "store", "Loja Online", "store",
            items=[
                Item(
                    "enter_store", "Entrar na Store", "XMB Store",
                    "store",
                    {"description": "Abre a interface completa da loja online — navegue, compre e baixe jogos e temas."},
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
                        "Servidor online" if store_client.health() else "Servidor offline"
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
    pygame.display.set_caption(config.get("system_name", "XMB-PY"))

    flags = pygame.FULLSCREEN if config.get("fullscreen") else pygame.RESIZABLE
    screen = pygame.display.set_mode((theme.SCREEN_W, theme.SCREEN_H), flags)
    clock = pygame.time.Clock()

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
                config["store_server_url"],
                timeout=config.get("store_request_timeout", 12),
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

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
