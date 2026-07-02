"""Daily FQC automation entry point.

Run:  python -m src.main

Flow:
  1. For each enabled MES site (CTV, DLT, JC): connect VPN if needed,
     log in with Playwright, open the Daily FQC page, read E03/E19/T11 and
     the overall defect rate.
  2. Append all of today's numbers as one new row in your Excel tracking
     file (without touching existing rows/charts).
  3. Export the dashboard chart to a PNG (Excel screenshot via xlwings /
     LibreOffice, or a matplotlib re-plot as a fallback).
  4. Send the PNG to your Telegram chat/group.

Any failure (login, missing selector, VPN, Excel, Telegram) sends a short
text alert to Telegram instead of failing silently, so you notice the same
day rather than finding out tomorrow that yesterday's row is missing.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import AppConfig, load_config
from src.excel_writer import append_daily_row
from src.chart_export import export_dashboard
from src.scraper import scrape_site
from src.telegram_sender import send_message, send_photo
from src.vpn import connect_vpn_if_configured


def setup_logging(log_dir: str) -> None:
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    log_file = Path(log_dir) / f"{date.today().isoformat()}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(log_file, encoding="utf-8")],
    )


def collect_all_metrics(cfg: AppConfig, headless: bool) -> dict[str, float]:
    """Returns a flat dict like {"CTV_E03": 1.2, ..., "JC_OVERALL": 2.4}."""
    values: dict[str, float] = {}
    vpn_connected = False

    for site_name, site in cfg.sites.items():
        if not site.enabled:
            logging.info("[%s] Disabled in config.yaml, skipping.", site_name)
            continue

        if site.requires_vpn and not vpn_connected:
            connect_vpn_if_configured()
            vpn_connected = True

        logging.info("[%s] Scraping Daily FQC page...", site_name)
        metrics = scrape_site(site, headless=headless)
        for metric_key, value in metrics.items():
            values[f"{site_name}_{metric_key}"] = value

    return values


def run(config_path: str = "config.yaml", headless: bool = True) -> None:
    cfg = load_config(config_path)
    setup_logging(cfg.output.log_dir)
    logger = logging.getLogger("main")
    today = date.today()

    try:
        values = collect_all_metrics(cfg, headless=headless)
        logger.info("Collected values: %s", values)

        append_daily_row(cfg.excel, today, values)

        dashboard_sheet = cfg.excel.dashboard_sheet_name or cfg.excel.sheet_name
        image_path = export_dashboard(
            excel_path=cfg.excel.path,
            sheet_name=dashboard_sheet,
            out_path=cfg.output.chart_image_path,
        )

        caption = cfg.telegram.caption_template.format(date=today.isoformat())
        send_photo(cfg.telegram, image_path, caption)

        logger.info("Daily FQC automation completed successfully.")
    except Exception as exc:  # noqa: BLE001 - top-level guard so failures are reported
        logger.exception("Daily FQC automation failed")
        try:
            send_message(cfg.telegram, f"Daily FQC automation FAILED on {today.isoformat()}: {exc}")
        except Exception:  # noqa: BLE001
            logger.exception("Additionally failed to send the Telegram failure alert.")
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Automate daily MES FQC report to Telegram.")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run the browser headed (visible) - useful the first time you set up selectors.",
    )
    args = parser.parse_args()
    run(config_path=args.config, headless=not args.headed)


if __name__ == "__main__":
    main()
