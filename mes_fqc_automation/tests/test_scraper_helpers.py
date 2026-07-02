import pytest

from src.scraper import ScrapeError, _extract_number


def test_extract_number_with_percent_sign_no_regex():
    assert _extract_number("1.23%", None) == pytest.approx(1.23)


def test_extract_number_with_regex():
    assert _extract_number("불량률: 2.45 %", r"([0-9.]+)") == pytest.approx(2.45)


def test_extract_number_with_whitespace():
    assert _extract_number("  0.9  ", None) == pytest.approx(0.9)


def test_extract_number_regex_no_match_raises():
    with pytest.raises(ScrapeError):
        _extract_number("no numbers here", r"([0-9.]+)")
