"""Log into an MES site with Playwright and scrape the Daily FQC numbers.

This is written to be generic: all the "where do I click / what do I read"
knowledge lives in config.yaml (see config.example.yaml), not in this file.
You should only need to edit config.yaml's selectors to point this at your
real CTV/DLT/JC pages - not this module.
"""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from tenacity import retry, stop_after_attempt, wait_fixed

if TYPE_CHECKING:
    from playwright.sync_api import Page

from src.config import METRIC_KEYS, SiteConfig

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_MS = 30_000


class ScrapeError(RuntimeError):
    pass


def _locator_for(page: "Page", selector: str, selector_type: str):
    if selector_type == "xpath":
        expr = selector if selector.startswith("xpath=") else f"xpath={selector}"
        return page.locator(expr)
    return page.locator(selector)


def _extract_number(raw_text: str, regex: str | None) -> float:
    text = raw_text.strip()
    if regex:
        match = re.search(regex, text)
        if not match:
            raise ScrapeError(f"regex {regex!r} did not match text {text!r}")
        text = match.group(1)
    else:
        text = text.replace("%", "").strip()
    return float(text)


@retry(stop=stop_after_attempt(3), wait=wait_fixed(3), reraise=True)
def login(page: "Page", site: SiteConfig) -> None:
    username, password = site.credentials()
    logger.info("[%s] Navigating to login page: %s", site.name, site.login.url)
    page.goto(site.login.url, timeout=DEFAULT_TIMEOUT_MS)

    page.fill(site.login.username_selector, username, timeout=DEFAULT_TIMEOUT_MS)
    page.fill(site.login.password_selector, password, timeout=DEFAULT_TIMEOUT_MS)
    page.click(site.login.submit_selector, timeout=DEFAULT_TIMEOUT_MS)

    if site.login.success_selector:
        page.wait_for_selector(site.login.success_selector, timeout=DEFAULT_TIMEOUT_MS)
    else:
        page.wait_for_load_state("networkidle", timeout=DEFAULT_TIMEOUT_MS)

    logger.info("[%s] Login successful.", site.name)


def goto_fqc_page(page: "Page", site: SiteConfig) -> None:
    fqc = site.fqc_page
    if fqc.url:
        logger.info("[%s] Navigating to Daily FQC page: %s", site.name, fqc.url)
        page.goto(fqc.url, timeout=DEFAULT_TIMEOUT_MS)
    for step_selector in fqc.navigation_steps:
        logger.info("[%s] Clicking navigation step: %s", site.name, step_selector)
        page.click(step_selector, timeout=DEFAULT_TIMEOUT_MS)

    if fqc.wait_for_selector:
        page.wait_for_selector(fqc.wait_for_selector, timeout=DEFAULT_TIMEOUT_MS)


def read_metrics(page: "Page", site: SiteConfig) -> dict[str, float]:
    results: dict[str, float] = {}
    for key in METRIC_KEYS:
        metric = site.metrics[key]
        locator = _locator_for(page, metric.selector, metric.selector_type)
        raw_text = locator.first.inner_text(timeout=DEFAULT_TIMEOUT_MS)
        value = _extract_number(raw_text, metric.regex)
        results[key] = value
        logger.info("[%s] %s = %s (raw text: %r)", site.name, key, value, raw_text)
    return results


def scrape_site(site: SiteConfig, headless: bool = True) -> dict[str, float]:
    """Log into `site` and return {"E03": .., "E19": .., "T11": .., "OVERALL": ..}."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        try:
            context = browser.new_context()
            page = context.new_page()
            login(page, site)
            goto_fqc_page(page, site)
            return read_metrics(page, site)
        finally:
            browser.close()
