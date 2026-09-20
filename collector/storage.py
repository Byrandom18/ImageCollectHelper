from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

APP_DIR_NAME = "ImageCollectHelper"
SECRET_KEYS = ("pexels_key", "unsplash_key", "pixabay_key")


def app_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    path = Path(base) / APP_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def settings_path() -> Path:
    return app_data_dir() / "settings.json"


def secrets_path() -> Path:
    return repo_root() / "secrets.json"


def seen_ids_path() -> Path:
    return app_data_dir() / "seen_ids.json"


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_secrets() -> dict[str, str]:
    data = load_json(secrets_path(), {})
    if not isinstance(data, dict):
        return {key: "" for key in SECRET_KEYS}
    return {key: str(data.get(key) or "") for key in SECRET_KEYS}


def save_secrets(data: dict[str, Any]) -> None:
    payload = {key: str(data.get(key) or "").strip() for key in SECRET_KEYS}
    save_json(secrets_path(), payload)


def load_settings() -> dict[str, Any]:
    data = load_json(settings_path(), {})
    if not isinstance(data, dict):
        data = {}

    secrets = load_secrets()
    migrated = False
    for key in SECRET_KEYS:
        old = str(data.pop(key, "") or "").strip()
        if old and not secrets.get(key):
            secrets[key] = old
            migrated = True
    if migrated:
        save_secrets(secrets)
        save_json(settings_path(), data)
    data.update(secrets)
    return data


def save_settings(data: dict[str, Any]) -> None:
    save_secrets(data)
    payload = {key: value for key, value in data.items() if key not in SECRET_KEYS}
    save_json(settings_path(), payload)


def load_seen_ids() -> set[str]:
    data = load_json(seen_ids_path(), [])
    if isinstance(data, list):
        return {str(item) for item in data}
    return set()


def save_seen_ids(ids: set[str]) -> None:
    save_json(seen_ids_path(), sorted(ids))
