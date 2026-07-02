"""End-to-end test of src/scraper.py against a local fake MES (Flask) app.

This proves the generic Playwright login -> navigate -> read-metrics flow
actually works, so once you point config.yaml's selectors at your real
CTV/DLT/JC pages, the same code path will work there too.

Requires `pip install flask playwright` and `playwright install chromium`.
Skipped automatically if either is unavailable (e.g. CI without browsers).
"""
from __future__ import annotations

import threading
import time

import pytest

flask = pytest.importorskip("flask")
pytest.importorskip("playwright")

from src.config import FqcPageConfig, LoginConfig, MetricSelector, SiteConfig
from src.scraper import scrape_site

from tests.fixtures.mock_mes_server import FQC_DATA, VALID_PASS, VALID_USER, app as mock_app

PORT = 5099


@pytest.fixture(scope="module")
def mock_server():
    server_thread = threading.Thread(
        target=lambda: mock_app.run(port=PORT, use_reloader=False),
        daemon=True,
    )
    server_thread.start()
    time.sleep(1.0)
    yield f"http://127.0.0.1:{PORT}"


def _site_config(base_url: str, monkeypatch) -> SiteConfig:
    monkeypatch.setenv("MOCK_USERNAME", VALID_USER)
    monkeypatch.setenv("MOCK_PASSWORD", VALID_PASS)

    return SiteConfig(
        name="MOCK",
        enabled=True,
        requires_vpn=False,
        base_url=base_url,
        login=LoginConfig(
            url=f"{base_url}/login",
            username_selector="#userId",
            password_selector="#password",
            submit_selector="#loginBtn",
            username_env="MOCK_USERNAME",
            password_env="MOCK_PASSWORD",
            success_selector="#gnbUserMenu",
        ),
        fqc_page=FqcPageConfig(
            url=f"{base_url}/quality/dailyFqc",
            navigation_steps=[],
            wait_for_selector="#fqcTable",
        ),
        metrics={
            "E03": MetricSelector(selector="#fqcTable [data-line='E03'] .defect-rate", regex=r"([0-9.]+)"),
            "E19": MetricSelector(selector="#fqcTable [data-line='E19'] .defect-rate", regex=r"([0-9.]+)"),
            "T11": MetricSelector(selector="#fqcTable [data-line='T11'] .defect-rate", regex=r"([0-9.]+)"),
            "OVERALL": MetricSelector(selector="#fqcTable .total-defect-rate", regex=r"([0-9.]+)"),
        },
    )


def test_scrape_site_against_mock_mes(mock_server, monkeypatch):
    site = _site_config(mock_server, monkeypatch)

    result = scrape_site(site, headless=True)

    assert result == pytest.approx(FQC_DATA)
