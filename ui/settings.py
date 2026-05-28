import json
import os
from pathlib import Path


_CONFIG_PATH = Path.home() / ".ocorrencias_config.json"

DEFAULTS = {
    "theme": "dark",
    "gemini_model": "gemini-2.5-flash",
    "last_dir": "",
    "geometry": None,
    "codigos_ocorrencias": "FA, AT, A-, SD, LC, AA, AP, LM, FE, 14, 13",
}


def get_path() -> Path:
    return _CONFIG_PATH


def load() -> dict:
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return dict(DEFAULTS)
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULTS)
    merged = dict(DEFAULTS)
    merged.update(data)
    return merged


def save(data: dict) -> str | None:
    try:
        current = load()
        current.update(data)
        tmp = _CONFIG_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(current, indent=2), encoding="utf-8")
        os.replace(tmp, _CONFIG_PATH)
        return None
    except OSError as e:
        return str(e)
