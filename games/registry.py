"""Registro de jogos instalados.

Cada jogo é uma subpasta dentro de games/ contendo:
  - game.json   manifesto com id, nome, descrição, ícone e arquivo de entrada
  - main.py     (ou outro nome, definido em "entry") implementando:
                    def run(screen, clock) -> bool
                onde screen é a superfície pygame compartilhada com a XMB e
                o retorno indica se o usuário pediu para fechar o sistema
                inteiro (True) ou apenas voltar ao menu (False).

Basta soltar uma nova pasta dentro de games/ seguindo esse formato que ela
aparece automaticamente na categoria "Jogos" da XMB — não é preciso editar
main.py.
"""
import importlib.util
import json
import os

GAMES_DIR = os.path.dirname(os.path.abspath(__file__))


def discover_games():
    """Escaneia games/ e retorna uma lista de dicts:
    {"id", "name", "description", "icon", "run"} para cada jogo válido
    encontrado (com game.json + arquivo de entrada + função run())."""
    games = []

    for entry in sorted(os.listdir(GAMES_DIR)):
        game_dir = os.path.join(GAMES_DIR, entry)
        manifest_path = os.path.join(game_dir, "game.json")

        if not os.path.isdir(game_dir) or not os.path.isfile(manifest_path):
            continue

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[games] manifesto inválido em '{entry}': {exc}")
            continue

        entry_file = manifest.get("entry", "main.py")
        entry_path = os.path.join(game_dir, entry_file)
        if not os.path.isfile(entry_path):
            print(f"[games] arquivo de entrada não encontrado para '{entry}': {entry_file}")
            continue

        module_name = f"games.{entry}.{os.path.splitext(entry_file)[0]}"
        spec = importlib.util.spec_from_file_location(module_name, entry_path)
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as exc:  # noqa: BLE001
            print(f"[games] falha ao carregar '{entry}': {exc}")
            continue

        run_func = getattr(module, "run", None)
        if run_func is None:
            print(f"[games] '{entry}' não define uma função run(screen, clock)")
            continue

        games.append(
            {
                "id": manifest.get("id", entry),
                "name": manifest.get("name", entry),
                "description": manifest.get("description", ""),
                "icon": manifest.get("icon", "game"),
                "run": run_func,
            }
        )

    return games


def uninstall_game(game_id):
    """Remove a pasta do jogo instalado. Retorna True se removeu.

    Não remove pastas especiais (common) nem o próprio registry.
    """
    import shutil

    protected = {"common", "__pycache__", "__init__.py"}
    for entry in os.listdir(GAMES_DIR):
        if entry in protected:
            continue
        game_dir = os.path.join(GAMES_DIR, entry)
        if not os.path.isdir(game_dir):
            continue
        manifest_path = os.path.join(game_dir, "game.json")
        gid = entry
        if os.path.isfile(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                gid = meta.get("id", entry)
            except (OSError, json.JSONDecodeError):
                pass
        if gid == game_id or entry == game_id:
            shutil.rmtree(game_dir)
            return True
    return False
