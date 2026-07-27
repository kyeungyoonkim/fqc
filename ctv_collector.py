"""
CTV MES browser automation: log in, select date range + line, Search, then
click the Excel button to download the export file for each line.

Downloaded files are saved to the path configured in `mes.ctv.export_file`
(with `{line}` replaced), so the existing parser in mes_automation.py can
read them without any change.

Because MES pages differ, selectors are read from config. For MFA/DUO you can
set `mes.ctv.login.manual: true` to log in by hand once; the script waits until
you press Enter in the console, then automates the per-line exports.
"""
from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path
from typing import Any

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover
    sync_playwright = None


def _fmt_date(day: dt.date, fmt: str) -> str:
    return day.strftime(fmt)


def _fill_first(page: Any, selectors: str, value: str) -> bool:
    for sel in [s.strip() for s in selectors.split(",") if s.strip()]:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0:
                loc.fill(value)
                return True
        except Exception:
            continue
    return False


def _click_first(page: Any, selectors: str) -> bool:
    for sel in [s.strip() for s in selectors.split(",") if s.strip()]:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0:
                loc.click()
                return True
        except Exception:
            continue
    return False


def collect_ctv_exports(cfg: dict[str, Any], start: dt.date, end: dt.date) -> list[Path]:
    """Download one export file per configured CTV line. Returns saved paths."""
    if sync_playwright is None:
        raise RuntimeError(
            "Playwright not installed. Run: pip install playwright && python -m playwright install"
        )

    ctv = cfg["mes"]["ctv"]
    sel = ctv.get("selectors", {})
    login_cfg = ctv.get("login", {}) if isinstance(ctv.get("login"), dict) else {}
    browser_cfg = cfg.get("browser", {})

    export_template = ctv.get("export_file", "").strip()
    if not export_template or "{line}" not in export_template:
        raise RuntimeError(
            "mes.ctv.export_file must contain '{line}', e.g. C:/Downloads/CTV_{line}.xlsx"
        )

    date_fmt = ctv.get("date_format", "%Y-%m-%d")
    lines = ctv.get("lines", [])
    headless = bool(browser_cfg.get("headless", False))
    nav_timeout = int(browser_cfg.get("timeout_ms", 60000))
    channel = str(browser_cfg.get("channel", "") or "").strip()

    saved: list[Path] = []
    with sync_playwright() as p:
        launch_kwargs: dict[str, Any] = {"headless": headless}
        if channel:
            # Use a system-installed browser (e.g. "msedge" or "chrome")
            # so no Chromium download is required behind corporate SSL.
            launch_kwargs["channel"] = channel
            logging.info("Launching system browser channel: %s", channel)
        browser = p.chromium.launch(**launch_kwargs)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        page.set_default_timeout(nav_timeout)

        logging.info("Opening CTV login: %s", ctv["login_url"])
        page.goto(ctv["login_url"])

        if login_cfg.get("manual", False):
            print("\n[ACTION] Log in to CTV MES in the opened browser.")
            print("         Approve DUO if prompted, and navigate to the Daily FQC page.")
            input("         When ready, press Enter here to continue...\n")
        else:
            _fill_first(page, sel.get("username_input", 'input[name="username"]'), ctv["username"])
            _fill_first(page, sel.get("password_input", 'input[name="password"]'), ctv["password"])
            _click_first(page, sel.get("login_button", 'button[type="submit"]'))
            page.wait_for_load_state("networkidle")
            if login_cfg.get("duo_required", False):
                print("\n[ACTION] Approve the DUO push on your phone.")
                input("         After approval + reaching Daily FQC page, press Enter...\n")

        daily_url = ctv.get("daily_fqc_url", "").strip()
        if daily_url:
            logging.info("Navigating to Daily FQC page: %s", daily_url)
            page.goto(daily_url)
            page.wait_for_load_state("networkidle")

        for line in lines:
            logging.info("CTV export for line %s (%s ~ %s)", line, start, end)
            _fill_first(page, sel.get("start_date_input", ""), _fmt_date(start, date_fmt))
            _fill_first(page, sel.get("end_date_input", ""), _fmt_date(end, date_fmt))
            _fill_first(page, sel.get("line_input", ""), line)

            if not _click_first(page, sel.get("search_button", 'button:has-text("Search")')):
                logging.warning("Search button not found for line %s", line)
            page.wait_for_load_state("networkidle")

            out_path = Path(export_template.format(line=line))
            out_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with page.expect_download(timeout=nav_timeout) as dl_info:
                    _click_first(page, sel.get("export_button", 'button:has-text("Excel")'))
                download = dl_info.value
                download.save_as(str(out_path))
                saved.append(out_path)
                logging.info("Saved CTV export: %s", out_path)
            except Exception as exc:  # noqa: BLE001
                shot = out_path.with_suffix(".error.png")
                try:
                    page.screenshot(path=str(shot))
                except Exception:
                    pass
                raise RuntimeError(
                    f"CTV export failed for line {line}: {exc}. Debug screenshot: {shot}"
                ) from exc

        context.close()
        browser.close()
    return saved
