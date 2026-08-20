"""Sessão local do usuário XMB-PY: credenciais e token persistidos em data/session.json."""
import json
import os
from pathlib import Path

SESSION_PATH = Path(__file__).resolve().parent.parent / "data" / "session.json"


def load_session():
    if not SESSION_PATH.exists():
        return {}
    try:
        with open(SESSION_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_session(data):
    SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SESSION_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def clear_session():
    if SESSION_PATH.exists():
        SESSION_PATH.unlink()


def get_token():
    return load_session().get("token")


def get_user():
    s = load_session()
    if not s.get("token"):
        return None
    return {
        "username": s.get("username"),
        "display_name": s.get("display_name"),
        "user_id": s.get("user_id"),
    }


def set_logged_in(token, user):
    save_session({
        "token": token,
        "username": user.get("username"),
        "display_name": user.get("display_name"),
        "user_id": user.get("id") or user.get("user_id"),
    })
