from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .config import PATHS, SEARCH_CONTEXT_KEY, SEARCH_KEYWORD
from .models import Listing


def ensure_runtime_dirs() -> None:
    PATHS.auth_dir.mkdir(parents=True, exist_ok=True)
    PATHS.data_dir.mkdir(parents=True, exist_ok=True)
    PATHS.others_dir.mkdir(parents=True, exist_ok=True)
    PATHS.profile_dir.mkdir(parents=True, exist_ok=True)


def load_json_file(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_json_file(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_baseline() -> list[Listing]:
    payload = load_json_file(PATHS.baseline_path)
    if not payload:
        return []
    if payload.get("context") != SEARCH_CONTEXT_KEY:
        return []
    items = payload.get("items", [])
    return [Listing.from_dict(item) for item in items]


def save_baseline(items: list[Listing]) -> None:
    payload = {
        "keyword": SEARCH_KEYWORD,
        "context": SEARCH_CONTEXT_KEY,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "items": [item.to_dict() for item in items],
    }
    save_json_file(PATHS.baseline_path, payload)


def load_seen_item_ids() -> set[str]:
    payload = load_json_file(PATHS.seen_ids_path)
    if not payload or not isinstance(payload, dict):
        return set()
    if payload.get("context") != SEARCH_CONTEXT_KEY:
        return set()
    item_ids = payload.get("item_ids", [])
    if not isinstance(item_ids, list):
        return set()
    return {str(item_id) for item_id in item_ids if str(item_id).strip()}


def save_seen_item_ids(item_ids: set[str]) -> None:
    payload = {
        "context": SEARCH_CONTEXT_KEY,
        "item_ids": sorted(item_ids),
        "count": len(item_ids),
    }
    save_json_file(PATHS.seen_ids_path, payload)
