from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

try:
    from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright
except ImportError:  # pragma: no cover - exercised via env-check and import tests
    BrowserContext = Page = Playwright = Any
    sync_playwright = None

if TYPE_CHECKING:
    from playwright.sync_api import BrowserContext as PlaywrightBrowserContext
    from playwright.sync_api import Page as PlaywrightPage
    from playwright.sync_api import Playwright as PlaywrightType

from .config import (
    CHROME_EXECUTABLE_PATH,
    DEFAULT_TIMEOUT_MS,
    GOOFISH_HOME_URL,
    GOOFISH_SEARCH_URL,
    LOGIN_TIMEOUT_MS,
    PATHS,
)
from .storage import ensure_runtime_dirs, save_json_file


LOGIN_TEXT_MARKERS = (
    "扫码登录",
    "手机登录",
    "登录",
    "Sign in",
)

COOKIE_EXPORT_KEYS = ("cookies", "Cookies")
METADATA_PATH = PATHS.auth_dir / "auth_metadata.json"
CAPTURE_MIN_WAIT_SECONDS = 15


def ensure_playwright_available() -> None:
    if sync_playwright is None:
        raise RuntimeError(
            "Playwright is not installed. Run 'pip install -r requirements.txt' and "
            "'python3 -m playwright install chromium' first."
        )


def auth_exists() -> bool:
    return PATHS.profile_dir.exists() and any(PATHS.profile_dir.iterdir())


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_session_storage() -> dict[str, str]:
    if not PATHS.session_storage_path.exists():
        return {}
    payload = _read_json(PATHS.session_storage_path)
    return payload if isinstance(payload, dict) else {}


def install_session_storage(context: BrowserContext, session_data: dict[str, str]) -> None:
    if not session_data:
        return
    payload = json.dumps(session_data, ensure_ascii=False)
    context.add_init_script(
        f"""
        (() => {{
          const payload = {payload};
          const allowedHosts = ["www.goofish.com", "goofish.com", ".goofish.com"];
          if (!allowedHosts.includes(window.location.hostname) && !window.location.hostname.endsWith(".goofish.com")) {{
            return;
          }}
          for (const [key, value] of Object.entries(payload)) {{
            window.sessionStorage.setItem(key, value);
          }}
        }})();
        """,
    )


def save_session_storage(page: Page) -> None:
    payload = page.evaluate("() => JSON.stringify(sessionStorage)")
    data = json.loads(payload) if payload else {}
    save_json_file(PATHS.session_storage_path, data)


def looks_logged_in(page: Page) -> bool:
    current_url = page.url.lower()
    if "login" in current_url or "passport" in current_url:
        return False

    content = page.content()
    markers_found = sum(marker in content for marker in LOGIN_TEXT_MARKERS)
    if markers_found >= 2:
        return False

    cookies = page.context.cookies()
    return any("goofish.com" in cookie.get("domain", "") for cookie in cookies)


def search_results_ready(page: Page) -> bool:
    content = page.locator("body").inner_text()
    if "立即登录" in content:
        return False
    if page.locator('a[href*="/item?id="]').count() > 0:
        return True
    return "加载中..." not in content and "1/1" not in content and "1/50" in content


def save_debug_screenshot(page: Page, prefix: str) -> str:
    ensure_runtime_dirs()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = PATHS.others_dir / f"{prefix}-{timestamp}.png"
    page.screenshot(path=str(target), full_page=False)
    return str(target)


def capture_initial_profile_screenshot(context: BrowserContext, prefix: str) -> str | None:
    try:
        page = context.pages[0] if context.pages else context.new_page()
        page.wait_for_timeout(1200)
        return save_debug_screenshot(page, prefix)
    except Exception:
        return None


def save_auth_snapshot(context: BrowserContext, page: Page) -> None:
    context.storage_state(
        path=str(PATHS.storage_state_path),
        indexed_db=True,
    )
    save_session_storage(page)


def _launch_profile_context(playwright: Playwright, headless: bool = False) -> BrowserContext:
    launch_kwargs = {
        "user_data_dir": str(PATHS.profile_dir),
        "headless": headless,
        "viewport": {"width": 1440, "height": 960},
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--start-maximized",
        ],
    }
    if CHROME_EXECUTABLE_PATH:
        chrome_path = Path(CHROME_EXECUTABLE_PATH).expanduser()
        if chrome_path.exists():
            launch_kwargs["executable_path"] = str(chrome_path)

    context = playwright.chromium.launch_persistent_context(
        **launch_kwargs,
    )
    context.set_default_timeout(DEFAULT_TIMEOUT_MS)
    return context


def _normalize_same_site(raw_value: Any) -> str:
    value = str(raw_value or "").strip().lower()
    mapping = {
        "strict": "Strict",
        "lax": "Lax",
        "none": "None",
        "no_restriction": "None",
        "unspecified": "Lax",
    }
    return mapping.get(value, "Lax")


def _normalize_expiry(raw_value: Any) -> float:
    if raw_value in (None, "", 0, "0"):
        return -1
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return -1


def _coerce_cookie(raw_cookie: dict[str, Any]) -> dict[str, Any]:
    domain = str(raw_cookie.get("domain") or "").strip()
    if not domain:
        raise ValueError("cookie 缺少 domain")

    path = str(raw_cookie.get("path") or "/").strip() or "/"
    name = str(raw_cookie.get("name") or "").strip()
    value = str(raw_cookie.get("value") or "")
    if not name:
        raise ValueError("cookie 缺少 name")

    return {
        "name": name,
        "value": value,
        "domain": domain,
        "path": path,
        "expires": _normalize_expiry(
            raw_cookie.get("expires", raw_cookie.get("expirationDate"))
        ),
        "httpOnly": bool(raw_cookie.get("httpOnly", False)),
        "secure": bool(raw_cookie.get("secure", False)),
        "sameSite": _normalize_same_site(raw_cookie.get("sameSite")),
    }


def _extract_cookie_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        if isinstance(payload.get("origins"), list) and isinstance(payload.get("cookies"), list):
            return payload["cookies"]
        for key in COOKIE_EXPORT_KEYS:
            cookies = payload.get(key)
            if isinstance(cookies, list):
                return cookies

    raise ValueError("无法识别登录态 JSON 格式。请提供 cookies 数组或 Playwright storage_state JSON。")


def import_auth_state(source_path: str) -> None:
    ensure_runtime_dirs()
    source = Path(source_path).expanduser().resolve()
    if not source.exists():
        raise RuntimeError(f"登录态文件不存在: {source}")

    payload = _read_json(source)
    cookies = [_coerce_cookie(cookie) for cookie in _extract_cookie_list(payload)]
    goofish_cookies = [
        cookie for cookie in cookies if "goofish.com" in cookie["domain"] or "taobao.com" in cookie["domain"]
    ]
    if not goofish_cookies:
        raise RuntimeError("导入文件里没有识别到闲鱼/淘宝相关 cookies。")

    storage_state = {"cookies": goofish_cookies, "origins": []}
    save_json_file(PATHS.storage_state_path, storage_state)
    save_json_file(PATHS.session_storage_path, {})
    save_json_file(
        METADATA_PATH,
        {
            "source_name": source.name,
            "cookie_count": len(goofish_cookies),
            "mode": "imported_cookie_json",
        },
    )


def capture_auth_state() -> None:
    ensure_runtime_dirs()
    ensure_playwright_available()
    with sync_playwright() as playwright:
        context = _launch_profile_context(playwright, headless=False)
        try:
            capture_initial_profile_screenshot(context, "capture-initial-open")
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(GOOFISH_HOME_URL, wait_until="domcontentloaded")
            print("请在打开的 Chrome 浏览器中扫码登录闲鱼，脚本会自动保存专用 profile。")
            deadline = time.time() + LOGIN_TIMEOUT_MS / 1000
            not_before = time.time() + CAPTURE_MIN_WAIT_SECONDS
            while time.time() < deadline:
                page.wait_for_timeout(1500)
                if time.time() < not_before:
                    continue
                if not looks_logged_in(page):
                    continue
                try:
                    verify_page = context.new_page()
                    verify_page.goto(GOOFISH_SEARCH_URL, wait_until="domcontentloaded")
                    verify_page.wait_for_timeout(3000)
                except Exception:
                    try:
                        verify_page.close()
                    except Exception:
                        pass
                    continue
                if search_results_ready(verify_page):
                    save_auth_snapshot(context, verify_page)
                    try:
                        verify_page.close()
                    except Exception:
                        pass
                    save_json_file(
                        METADATA_PATH,
                        {
                            "source": "captured_via_qr_login",
                            "cookie_count": len(context.cookies()),
                            "mode": "persistent_chrome_profile",
                        },
                    )
                    print("登录成功，专用 Chrome profile 已保存。")
                    return
                if "立即登录" in verify_page.locator("body").inner_text():
                    screenshot_path = save_debug_screenshot(verify_page, "capture-login-prompt")
                    print(f"检测到继续登录提示，已截图: {screenshot_path}")
                try:
                    verify_page.close()
                except Exception:
                    pass
            raise RuntimeError("登录超时，未检测到有效的闲鱼登录状态。")
        finally:
            context.close()


def open_authenticated_context(playwright: Playwright, headless: bool = False) -> BrowserContext:
    ensure_runtime_dirs()
    if not auth_exists():
        raise RuntimeError("未找到可复用的 Chrome 登录 profile，请先执行 capture-state。")

    context = _launch_profile_context(playwright, headless=headless)
    install_session_storage(context, load_session_storage())
    return context


def validate_auth_state() -> None:
    ensure_playwright_available()
    with sync_playwright() as playwright:
        context = open_authenticated_context(playwright, headless=False)
        try:
            capture_initial_profile_screenshot(context, "check-initial-open")
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(GOOFISH_HOME_URL, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
            if not looks_logged_in(page):
                raise RuntimeError("当前 Chrome profile 登录态已失效，请重新执行 capture-state。")
            save_auth_snapshot(context, page)
        finally:
            context.close()
