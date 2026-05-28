import json
import os
from pathlib import Path


_HISTORY_PATH = Path.home() / ".ocorrencias_history.json"

MAX_ENTRIES = 500


def get_path() -> Path:
    return _HISTORY_PATH


def load() -> list[dict]:
    try:
        with open(_HISTORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return []
        return data
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []


def _write(data: list[dict]) -> str | None:
    try:
        tmp = _HISTORY_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, _HISTORY_PATH)
        return None
    except OSError as e:
        return str(e)


def append(entry: dict) -> str | None:
    data = load()
    data.append(entry)
    if len(data) > MAX_ENTRIES:
        data = data[-MAX_ENTRIES:]
    return _write(data)


def remove(index: int) -> str | None:
    data = load()
    if 0 <= index < len(data):
        del data[index]
        return _write(data)
    return None


def clear() -> str | None:
    return _write([])
