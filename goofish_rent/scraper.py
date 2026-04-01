from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, urlparse

try:
    from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright
except ImportError:  # pragma: no cover - allows env-check and import-time tests
    Page = Any
    sync_playwright = None

    class PlaywrightTimeoutError(Exception):
        pass

from .auth import ensure_playwright_available, open_authenticated_context, save_auth_snapshot, save_debug_screenshot, validate_auth_state
from .config import (
    FIXED_NEARBY_LOCATION,
    GOOFISH_SEARCH_URL,
    MAX_PRICE,
    MAX_RESULTS,
    MIN_PRICE,
    NEARBY_RADIUS_KM,
)
from .models import Listing


NEARBY_RADIUS_LABELS = ("1km", "5km", "10km", "15km", "50km")
NEARBY_PANEL_STATIC_TEXTS = {
    "选地区",
    "搜附近",
    "常用地址",
    "查看",
    "区域",
    "综合",
    "新发布",
    "最新",
    "价格",
    "-",
    "确定",
}


def safe_get(data: dict[str, Any], *keys: str, default: Any = "") -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def normalize_url(raw_url: str) -> str:
    if not raw_url:
        return ""
    if raw_url.startswith("fleamarket://"):
        return raw_url.replace("fleamarket://", "https://www.goofish.com/", 1)
    if raw_url.startswith("//"):
        return f"https:{raw_url}"
    return raw_url


def extract_item_id(raw_url: str, fallback: str = "") -> str:
    normalized = normalize_url(raw_url)
    parsed = urlparse(normalized)
    query = parse_qs(parsed.query)
    for key in ("itemId", "id", "item_id"):
        value = query.get(key)
        if value and value[0]:
            return value[0]

    for pattern in (r"/item(?:s)?/(\d+)", r"[?&]itemId=(\d+)", r"[?&]id=(\d+)"):
        match = re.search(pattern, normalized)
        if match:
            return match.group(1)

    return fallback or normalized


def parse_price(parts: Any) -> str:
    if isinstance(parts, list):
        text = "".join(
            str(part.get("text", ""))
            for part in parts
            if isinstance(part, dict)
        )
        return text.replace("当前价", "").strip() or "价格未知"
    if isinstance(parts, str) and parts.strip():
        return parts.strip()
    return "价格未知"


def parse_area(main_data: dict[str, Any]) -> str:
    for key in ("area", "location", "tradeLocation", "city"):
        value = safe_get(main_data, key, default="")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "地区未知"


def parse_area_from_text(lines: list[str]) -> str:
    for line in reversed(lines):
        candidate = line.strip()
        if not candidate:
            continue
        if candidate.startswith("卖家信用"):
            continue
        if "想要" in candidate:
            continue
        if "发布" in candidate:
            continue
        if candidate.startswith("¥") or re.fullmatch(r"[\d./月]+", candidate):
            continue
        if len(candidate) <= 12:
            return candidate
    return "地区未知"


def parse_price_from_text(text: str) -> str:
    compact = " ".join(text.split())
    monthly = re.search(r"¥\s*([\d.]+)\s*/月", compact)
    if monthly:
        return f"¥{monthly.group(1)}/月"
    plain = re.search(r"¥\s*([\d.]+)", compact)
    if plain:
        return f"¥{plain.group(1)}"
    return "价格未知"


def listing_from_result(item: dict[str, Any]) -> Listing | None:
    main = safe_get(item, "data", "item", "main", default={})
    ex_content = safe_get(main, "exContent", default={})
    title = safe_get(ex_content, "title", default="").strip()
    raw_url = safe_get(main, "targetUrl", default="")
    url = normalize_url(raw_url)
    item_id = extract_item_id(raw_url, fallback=title)
    if not title or not url or not item_id:
        return None

    return Listing(
        item_id=item_id,
        title=title,
        price=parse_price(safe_get(ex_content, "price", default=[])),
        area=parse_area(ex_content),
        url=url,
    )


def click_first_available(page: Page, labels: list[str]) -> bool:
    for label in labels:
        locator = page.get_by_text(label, exact=False).first
        try:
            locator.wait_for(timeout=2000)
            locator.click()
            page.wait_for_timeout(800)
            return True
        except PlaywrightTimeoutError:
            continue
        except Exception:
            continue
    return False


def compact_text(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def collect_visible_text_nodes(page: Page) -> list[dict[str, float | str]]:
    return page.evaluate(
        """
        () => {
          const nodes = [];
          const seen = new Set();
          for (const el of document.querySelectorAll('div, span, p, button, li')) {
            const rawText = (el.innerText || '').replace(/\\s+/g, ' ').trim();
            if (!rawText || rawText.length > 120) {
              continue;
            }
            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            if (
              style.display === 'none' ||
              style.visibility === 'hidden' ||
              rect.width < 8 ||
              rect.height < 8
            ) {
              continue;
            }
            const key = [rawText, Math.round(rect.x), Math.round(rect.y), Math.round(rect.width), Math.round(rect.height)].join('|');
            if (seen.has(key)) {
              continue;
            }
            seen.add(key);
            nodes.push({
              text: rawText,
              x: rect.x,
              y: rect.y,
              width: rect.width,
              height: rect.height,
            });
          }
          return nodes;
        }
        """
    )


def click_box_center(page: Page, node: dict[str, float | str]) -> None:
    page.mouse.click(
        float(node["x"]) + float(node["width"]) / 2,
        float(node["y"]) + float(node["height"]) / 2,
    )


def click_panel_text(
    page: Page,
    *,
    text: str,
    input_box: dict[str, float],
    y_min: float,
    match_mode: str = "exact",
) -> bool:
    x_min = float(input_box.get("x", 0)) - 40
    x_max = float(input_box.get("x", 0)) + float(input_box.get("width", 0)) + 40
    nodes = collect_visible_text_nodes(page)
    candidates = [
        node
        for node in nodes
        if (
            compact_text(str(node["text"])) == compact_text(text)
            if match_mode == "exact"
            else compact_text(str(node["text"])).startswith(compact_text(text))
        )
        and x_min <= float(node["x"]) <= x_max
        and float(node["y"]) >= y_min
    ]
    candidates.sort(key=lambda node: (float(node["y"]), float(node["x"])))
    for node in candidates:
        click_box_center(page, node)
        return True
    return False


def click_apply_nearby_button(page: Page, input_box: dict[str, float], nearby_input: Any) -> bool:
    center_x = float(input_box.get("x", 0)) + float(input_box.get("width", 0)) / 2
    base_y = float(input_box.get("y", 0)) + 415
    for delta_y in (0, -12, 12):
        page.mouse.click(center_x, base_y + delta_y)
        try:
            nearby_input.wait_for(state="hidden", timeout=3_000)
            return True
        except Exception:
            continue
    return False


def select_address_suggestion(page: Page, input_bottom: float) -> str | None:
    target = compact_text(FIXED_NEARBY_LOCATION)
    nodes = collect_visible_text_nodes(page)
    candidates = [
        node
        for node in nodes
        if target[:4] in compact_text(str(node["text"]))
        and input_bottom <= float(node["y"]) <= input_bottom + 260
    ]
    candidates.sort(key=lambda node: (float(node["y"]), float(node["x"])))
    for node in candidates:
        click_box_center(page, node)
        return str(node["text"])
    return None


def select_nearby_result(page: Page, input_bottom: float, first_pick: str | None) -> bool:
    footer_box = page.get_by_text("1km", exact=True).first.bounding_box() or {}
    footer_top = float(footer_box.get("y", input_bottom + 400))
    seen_text = compact_text(first_pick or "")
    nodes = collect_visible_text_nodes(page)
    candidates: list[dict[str, float | str]] = []
    for node in nodes:
        text = str(node["text"]).strip()
        compact = compact_text(text)
        y = float(node["y"])
        if not text:
            continue
        if y <= input_bottom + 70 or y >= footer_top - 10:
            continue
        if compact in {compact_text(label) for label in NEARBY_RADIUS_LABELS}:
            continue
        if compact in {compact_text(label) for label in NEARBY_PANEL_STATIC_TEXTS}:
            continue
        if compact == compact_text(FIXED_NEARBY_LOCATION) or compact == seen_text:
            continue
        candidates.append(node)

    candidates.sort(key=lambda node: (float(node["y"]), float(node["x"])))
    for node in candidates:
        click_box_center(page, node)
        return True
    return False


def apply_latest_filter(page: Page) -> None:
    try:
        page.get_by_text("新发布", exact=True).first.click(timeout=2_000)
        page.wait_for_timeout(800)
        page.get_by_text("最新", exact=True).first.click(timeout=2_000)
        page.wait_for_timeout(2_000)
    except Exception:
        # Keep the default result ordering if the menu structure changes.
        return


def apply_price_filter(page: Page) -> None:
    try:
        page.get_by_text("价格", exact=True).first.click(timeout=2_000)
        page.wait_for_timeout(500)
        inputs = page.locator("input")
        inputs.nth(1).fill(str(MIN_PRICE))
        inputs.nth(2).fill(str(MAX_PRICE))
        page.get_by_text("确定", exact=True).first.click(timeout=2_000)
        page.wait_for_timeout(2_000)
    except Exception:
        return


def apply_nearby_filter(page: Page) -> None:
    try:
        page.locator("div.areaTextContainer--IQ5moIFF").first.click(timeout=2_000)
        page.wait_for_timeout(800)
        page.locator("div.tabStepItemText--Ghb1cxlF").filter(has_text="搜附近").first.click(timeout=2_000)
        page.wait_for_timeout(800)
        nearby_input = page.get_by_placeholder("搜索地点").first
        nearby_input.fill(FIXED_NEARBY_LOCATION)
        page.wait_for_timeout(1_500)
        input_box = nearby_input.bounding_box() or {}
        input_bottom = float(input_box.get("y", 0)) + float(input_box.get("height", 0))
        first_pick = select_address_suggestion(page, input_bottom)
        if first_pick:
            page.wait_for_timeout(1_200)
        select_nearby_result(page, input_bottom, first_pick)
        page.wait_for_timeout(800)
        input_box = nearby_input.bounding_box() or input_box
        click_panel_text(
            page,
            text=f"{NEARBY_RADIUS_KM}km",
            input_box=input_box,
            y_min=input_bottom + 180,
        )
        page.wait_for_timeout(500)
        if not click_apply_nearby_button(page, input_box, nearby_input):
            if not click_panel_text(
                page,
                text="查看",
                input_box=input_box,
                y_min=input_bottom + 220,
                match_mode="startswith",
            ):
                page.get_by_text("查看", exact=False).last.click(timeout=2_000)
            nearby_input.wait_for(state="hidden", timeout=5_000)
        page.wait_for_timeout(3_000)
    except Exception:
        save_debug_screenshot(page, "check-nearby-filter")
        return


def listing_from_dom_card(href: str, text: str) -> Listing | None:
    normalized_url = normalize_url(href)
    item_id = extract_item_id(normalized_url)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines or not item_id or not normalized_url:
        return None

    title = lines[0]
    return Listing(
        item_id=item_id,
        title=title,
        price=parse_price_from_text(text),
        area=parse_area_from_text(lines),
        url=normalized_url,
    )


def collect_dom_results(page: Page) -> list[Listing]:
    anchors = page.locator('a[href*="/item?id="]')
    anchor_count = min(anchors.count(), MAX_RESULTS)
    items: list[Listing] = []
    seen_ids: set[str] = set()
    for index in range(anchor_count):
        anchor = anchors.nth(index)
        href = anchor.get_attribute("href") or ""
        text = anchor.inner_text().strip()
        listing = listing_from_dom_card(href, text)
        if not listing or listing.item_id in seen_ids:
            continue
        seen_ids.add(listing.item_id)
        items.append(listing)
    return items


def wait_for_search_results(page: Page) -> None:
    anchors = page.locator('a[href*="/item?id="]')
    try:
        anchors.first.wait_for(timeout=15_000)
    except PlaywrightTimeoutError:
        screenshot_path = save_debug_screenshot(page, "check-no-results")
        raise RuntimeError(f"搜索结果超时未出现，已截图: {screenshot_path}") from None


def collect_latest_rent_listings() -> list[Listing]:
    validate_auth_state()
    ensure_playwright_available()
    with sync_playwright() as playwright:
        context = open_authenticated_context(playwright, headless=False)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(GOOFISH_SEARCH_URL, wait_until="domcontentloaded")
        wait_for_search_results(page)
        page.wait_for_timeout(1000)
        apply_latest_filter(page)
        apply_price_filter(page)
        apply_nearby_filter(page)
        wait_for_search_results(page)

        items = collect_dom_results(page)

        if len(items) < MAX_RESULTS:
            try:
                page.mouse.wheel(0, 2000)
                page.wait_for_timeout(3000)
                items = collect_dom_results(page)
            except Exception:
                pass

        save_auth_snapshot(context, page)
        context.close()

        if not items:
            raise RuntimeError("未抓取到搜索结果，可能是页面结构变化或登录态异常。")
        return items


def diff_new_items(current: list[Listing], seen_item_ids: set[str]) -> list[Listing]:
    return [item for item in current if item.item_id not in seen_item_ids]
