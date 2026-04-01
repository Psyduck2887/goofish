from __future__ import annotations

import argparse
import shutil
import json
import platform
import sys
from pathlib import Path

from .auth import capture_auth_state, import_auth_state
from .scraper import collect_latest_rent_listings, diff_new_items
from .config import CHROME_EXECUTABLE_PATH, ENV_FILE_PATH, FIXED_NEARBY_LOCATION, MAX_PRICE, MIN_PRICE, NEARBY_RADIUS_KM, ROOT_DIR, SEARCH_KEYWORD
from .storage import (
    ensure_runtime_dirs,
    load_baseline,
    load_seen_item_ids,
    save_baseline,
    save_seen_item_ids,
)


ENV_EXAMPLE_PATH = ROOT_DIR / ".env.example"


def build_env_check() -> dict:
    issues: list[str] = []
    chrome_path = CHROME_EXECUTABLE_PATH or "playwright-managed chromium"
    try:
        import playwright  # noqa: F401

        playwright_available = True
    except ImportError:
        playwright_available = False
        issues.append("Python package 'playwright' is not installed.")

    payload = {
        "python_version": platform.python_version(),
        "playwright_installed": playwright_available,
        "chrome_path": chrome_path,
        "config": {
            "keyword": SEARCH_KEYWORD,
            "min_price": MIN_PRICE,
            "max_price": MAX_PRICE,
            "nearby_radius_km": NEARBY_RADIUS_KM,
            "nearby_location": FIXED_NEARBY_LOCATION,
        },
        "issues": issues,
        "ready": not issues,
    }
    return payload


def build_init_config_payload(created: bool) -> dict:
    return {
        "config_path": str(ENV_FILE_PATH),
        "template_path": str(ENV_EXAMPLE_PATH),
        "created": created,
        "message": (
            "Created .env from .env.example. Edit the values once, then run 'python3 -m goofish_rent env-check'."
            if created
            else ".env already exists. Edit it if needed, then run 'python3 -m goofish_rent env-check'."
        ),
    }


def build_payload(*, status: str, items: list, message: str) -> dict:
    return {
        "status": status,
        "notify": bool(items),
        "message": message,
        "items": [item.to_dict() for item in items],
    }


def emit_check_result(
    *,
    json_mode: bool,
    status: str,
    items: list,
    message: str,
) -> None:
    if json_mode:
        print(json.dumps(build_payload(status=status, items=items, message=message), ensure_ascii=False))
        return

    if not items:
        print(message)
        return

    for item in items:
        print(f"{item.title} | {item.price} | {item.area} | {item.url}")


def handle_import_state(args: argparse.Namespace) -> int:
    import_auth_state(args.path)
    print("登录态导入成功。")
    return 0


def handle_capture_state(_: argparse.Namespace) -> int:
    capture_auth_state()
    return 0


def handle_env_check(_: argparse.Namespace) -> int:
    print(json.dumps(build_env_check(), ensure_ascii=False, indent=2))
    return 0


def handle_init_config(_: argparse.Namespace) -> int:
    if not ENV_EXAMPLE_PATH.exists():
        raise RuntimeError(f"Missing template file: {ENV_EXAMPLE_PATH}")

    created = False
    if not ENV_FILE_PATH.exists():
        shutil.copyfile(ENV_EXAMPLE_PATH, ENV_FILE_PATH)
        created = True

    print(json.dumps(build_init_config_payload(created), ensure_ascii=False, indent=2))
    return 0


def run_check() -> tuple[str, list, str]:
    ensure_runtime_dirs()
    baseline = load_baseline()
    seen_item_ids = load_seen_item_ids()
    current = collect_latest_rent_listings()
    if not seen_item_ids and baseline:
        seen_item_ids = {item.item_id for item in baseline}

    new_items = diff_new_items(current, seen_item_ids)
    save_baseline(current)
    save_seen_item_ids(seen_item_ids | {item.item_id for item in current})

    if not baseline:
        return (
            "initialized",
            [],
            "首次抓取完成，已建立基线。",
        )

    if not new_items:
        return (
            "no_new_items",
            [],
            "暂无新的符合条件的租房信息",
        )

    return (
        "new_items_found",
        new_items,
        f"发现 {len(new_items)} 条新的符合条件的租房信息",
    )


def handle_check(args: argparse.Namespace) -> int:
    status, items, message = run_check()
    emit_check_result(
        json_mode=args.json,
        status=status,
        items=items,
        message=message,
    )
    return 0


def handle_skill_check(_: argparse.Namespace) -> int:
    try:
        status, items, message = run_check()
        print(json.dumps(build_payload(status=status, items=items, message=message), ensure_ascii=False))
        return 0
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        text = str(exc)
        status = "error"
        if "capture-state" in text or "登录" in text or "profile" in text:
            status = "needs_login"
        print(
            json.dumps(
                build_payload(status=status, items=[], message=text),
                ensure_ascii=False,
            )
        )
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="goofish_rent",
        description="Goofish rent watcher MVP",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    import_parser = subparsers.add_parser(
        "import-state",
        help="Import exported Xianyu/Goofish login state JSON",
    )
    import_parser.add_argument("path", help="Path to exported cookie or storage_state JSON")
    import_parser.set_defaults(handler=handle_import_state)

    capture_parser = subparsers.add_parser(
        "capture-state",
        help="Open browser for QR login and export auth state",
    )
    capture_parser.set_defaults(handler=handle_capture_state)

    check_parser = subparsers.add_parser("check", help="Fetch latest items and print diff")
    check_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON output",
    )
    check_parser.set_defaults(handler=handle_check)

    skill_parser = subparsers.add_parser(
        "skill-check",
        help="Run a stable JSON interface for OpenClaw skills",
    )
    skill_parser.set_defaults(handler=handle_skill_check)

    env_check_parser = subparsers.add_parser(
        "env-check",
        help="Print installation and configuration checks",
    )
    env_check_parser.set_defaults(handler=handle_env_check)

    init_config_parser = subparsers.add_parser(
        "init-config",
        help="Create a local .env file from .env.example if it does not exist",
    )
    init_config_parser.set_defaults(handler=handle_init_config)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except KeyboardInterrupt:
        print("已中断。", file=sys.stderr)
        return 130
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
