from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote


ROOT_DIR = Path(__file__).resolve().parent.parent
AUTH_DIR = ROOT_DIR / "auth"
DATA_DIR = ROOT_DIR / "data"
OTHERS_DIR = ROOT_DIR / "others"
PROFILE_DIR = AUTH_DIR / "browser_profile"
STORAGE_STATE_PATH = AUTH_DIR / "storage_state.json"
SESSION_STORAGE_PATH = AUTH_DIR / "session_storage.json"
BASELINE_PATH = DATA_DIR / "latest_results.json"
SEEN_IDS_PATH = DATA_DIR / "seen_item_ids.json"
ENV_FILE_PATH = ROOT_DIR / ".env"


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


_load_dotenv(ENV_FILE_PATH)


def _read_str_env(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value or default


def _read_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


SEARCH_KEYWORD = _read_str_env("GOOFISH_SEARCH_KEYWORD", "转租")
MIN_PRICE = _read_int_env("GOOFISH_MIN_PRICE", 1800)
MAX_PRICE = _read_int_env("GOOFISH_MAX_PRICE", 2400)
NEARBY_RADIUS_KM = _read_int_env("GOOFISH_NEARBY_RADIUS_KM", 5)
FIXED_NEARBY_LOCATION = _read_str_env("GOOFISH_NEARBY_LOCATION", "示例地址")
SORT_MODE = _read_str_env("GOOFISH_SORT_MODE", "latest")
SEARCH_CONTEXT_VERSION = "v2_fixed_address_confirmed"
MAX_RESULTS = 20
LOGIN_TIMEOUT_MS = 5 * 60 * 1000
DEFAULT_TIMEOUT_MS = 15_000
GOOFISH_HOME_URL = "https://www.goofish.com/"
GOOFISH_SEARCH_URL = f"{GOOFISH_HOME_URL}search?q={quote(SEARCH_KEYWORD)}"
SEARCH_API_HINT = "idlemtopsearch.pc.search"
SEARCH_CONTEXT_KEY = (
    f"version={SEARCH_CONTEXT_VERSION}|keyword={SEARCH_KEYWORD}|price={MIN_PRICE}-{MAX_PRICE}|radius_km={NEARBY_RADIUS_KM}|sort={SORT_MODE}|location={FIXED_NEARBY_LOCATION}"
)
CHROME_EXECUTABLE_PATH = os.getenv("GOOFISH_CHROME_PATH", "").strip()


@dataclass(frozen=True)
class AppPaths:
    root_dir: Path = ROOT_DIR
    auth_dir: Path = AUTH_DIR
    data_dir: Path = DATA_DIR
    others_dir: Path = OTHERS_DIR
    profile_dir: Path = PROFILE_DIR
    storage_state_path: Path = STORAGE_STATE_PATH
    session_storage_path: Path = SESSION_STORAGE_PATH
    baseline_path: Path = BASELINE_PATH
    seen_ids_path: Path = SEEN_IDS_PATH


PATHS = AppPaths()
