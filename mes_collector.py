"""
Generic MES browser automation: (optionally connect VPN) -> log in -> select
date range + line -> Search -> click the Excel button to download the export
file, for every line configured under a site (`mes.ctv`, `mes.dlt`, ...).

Downloaded files are saved to the path configured in `mes.<site>.export_file`
(with `{line}` replaced), so the existing parser in `mes_automation.py` can
read them without any change.

Because MES pages differ per site, selectors are read from `config.yaml`.
For MFA/DUO you can set `mes.<site>.login.manual: true` to log in by hand
once; the script waits until you press Enter in the console, then automates
the per-line Search + Excel export.

JC is a desktop client (not a web page), so it is intentionally NOT handled
here - see README for the CSV/pywinauto fallback for JC.
"""
from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path
from typing import Any

from vpn import connect_vpn_if_configured

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover
    sync_playwright = None

# Sites that can be driven through a normal web browser. JC is excluded
# because it is a desktop client - see README.
WEB_SITES = ("ctv", "dlt")


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


def collect_site_exports(
    site_name: str, site_cfg: dict[str, Any], browser_cfg: dict[str, Any], start: dt.date, end: dt.date
) -> list[Path]:
    """Log into `site_name` (e.g. 'CTV', 'DLT') and download one export file per
    configured line. Returns the list of saved file paths."""
    if sync_playwright is None:
        raise RuntimeError(
            "Playwright not installed. Run: pip install playwright && python -m playwright install"
        )

    sel = site_cfg.get("selectors", {})
    login_cfg = site_cfg.get("login", {}) if isinstance(site_cfg.get("login"), dict) else {}

    export_template = site_cfg.get("export_file", "").strip()
    if not export_template or "{line}" not in export_template:
        raise RuntimeError(
            f"mes.{site_name.lower()}.export_file must contain '{{line}}', "
            f"e.g. C:/Downloads/{site_name}_{{line}}.xlsx"
        )

    date_fmt = site_cfg.get("date_format", "%Y-%m-%d")
    lines = site_cfg.get("lines", [])
    headless = bool(browser_cfg.get("headless", False))
    nav_timeout = int(browser_cfg.get("timeout_ms", 60000))
    channel = str(browser_cfg.get("channel", "") or "").strip()

    # Connect VPN first, if this site needs one (typically DLT/JC).
    connect_vpn_if_configured(site_name, site_cfg)

    saved: list[Path] = []
    with sync_playwright() as p:
        launch_kwargs: dict[str, Any] = {"headless": headless}
        if channel:
            # Use a system-installed browser (e.g. "msedge" or "chrome")
            # so no Chromium download is required behind corporate SSL.
            launch_kwargs["channel"] = channel
            logging.info("[%s] Launching system browser channel: %s", site_name, channel)
        browser = p.chromium.launch(**launch_kwargs)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        page.set_default_timeout(nav_timeout)

        try:
            logging.info("[%s] Opening login page: %s", site_name, site_cfg["login_url"])
            page.goto(site_cfg["login_url"])

            if login_cfg.get("manual", False):
                print(f"\n[ACTION] {site_name}: log in by hand in the opened browser.")
                print("         Approve DUO if prompted, and navigate to the Daily FQC page.")
                input("         When ready, press Enter here to continue...\n")
            else:
                _fill_first(page, sel.get("username_input", 'input[name="username"]'), site_cfg["username"])
                _fill_first(page, sel.get("password_input", 'input[name="password"]'), site_cfg["password"])
                _click_first(page, sel.get("login_button", 'button[type="submit"]'))
                page.wait_for_load_state("networkidle")
                if login_cfg.get("duo_required", False):
                    print(f"\n[ACTION] {site_name}: approve the DUO push on your phone.")
                    input("         After approval + reaching Daily FQC page, press Enter...\n")

            daily_url = site_cfg.get("daily_fqc_url", "").strip()
            if daily_url:
                logging.info("[%s] Navigating to Daily FQC page: %s", site_name, daily_url)
                page.goto(daily_url)
                page.wait_for_load_state("networkidle")

            for line in lines:
                logging.info("[%s] Export for line %s (%s ~ %s)", site_name, line, start, end)
                _fill_first(page, sel.get("start_date_input", ""), _fmt_date(start, date_fmt))
                _fill_first(page, sel.get("end_date_input", ""), _fmt_date(end, date_fmt))
                _fill_first(page, sel.get("line_input", ""), line)

                if not _click_first(page, sel.get("search_button", 'button:has-text("Search")')):
                    logging.warning("[%s] Search button not found for line %s", site_name, line)
                page.wait_for_load_state("networkidle")

                out_path = Path(export_template.format(line=line))
                out_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    with page.expect_download(timeout=nav_timeout) as dl_info:
                        _click_first(page, sel.get("export_button", 'button:has-text("Excel")'))
                    download = dl_info.value
                    download.save_as(str(out_path))
                    saved.append(out_path)
                    logging.info("[%s] Saved export: %s", site_name, out_path)
                except Exception as exc:  # noqa: BLE001
                    shot = out_path.with_suffix(".error.png")
                    try:
                        page.screenshot(path=str(shot))
                    except Exception:
                        pass
                    raise RuntimeError(
                        f"{site_name} export failed for line {line}: {exc}. Debug screenshot: {shot}"
                    ) from exc
        finally:
            context.close()
            browser.close()
    return saved


def collect_all_web_exports(cfg: dict[str, Any], start: dt.date, end: dt.date) -> list[Path]:
    """Run `collect_site_exports` for every enabled web-based site (CTV, DLT)."""
    browser_cfg = cfg.get("browser", {})
    saved: list[Path] = []
    for site in WEB_SITES:
        site_cfg = cfg["mes"].get(site, {})
        if not site_cfg.get("enabled", False):
            continue
        if not site_cfg.get("export_file", "").strip():
            logging.info("[%s] No export_file configured - skipping auto-export for this site.", site.upper())
            continue
        saved.extend(collect_site_exports(site.upper(), site_cfg, browser_cfg, start, end))
    return saved


# Backwards-compatible alias used by earlier scripts/docs.
def collect_ctv_exports(cfg: dict[str, Any], start: dt.date, end: dt.date) -> list[Path]:
    return collect_site_exports("CTV", cfg["mes"]["ctv"], cfg.get("browser", {}), start, end)
