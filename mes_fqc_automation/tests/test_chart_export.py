from datetime import date
from pathlib import Path

import pytest

pytest.importorskip("matplotlib")

from src.chart_export import export_dashboard, export_with_matplotlib


def test_export_with_matplotlib_creates_png(tmp_path):
    out_path = tmp_path / "chart.png"
    dates = [date(2026, 6, 29), date(2026, 6, 30), date(2026, 7, 1)]
    series = {
        "CTV Overall": [1.0, 1.2, 0.9],
        "DLT Overall": [2.0, 1.8, 1.5],
        "JC Overall": [0.5, 0.6, 0.4],
    }

    result_path = export_with_matplotlib(dates, series, str(out_path))

    assert result_path == out_path
    assert out_path.exists()
    assert out_path.stat().st_size > 0


def test_export_dashboard_falls_back_to_matplotlib_when_excel_unavailable(tmp_path):
    out_path = tmp_path / "dashboard.png"
    dates = [date(2026, 7, 1), date(2026, 7, 2)]
    series = {"CTV Overall": [1.0, 1.1]}

    result_path = export_dashboard(
        excel_path="/nonexistent/path.xlsx",
        sheet_name="Dashboard",
        out_path=str(out_path),
        matplotlib_fallback_data=(dates, series),
    )

    assert Path(result_path).exists()
