"""Turn the "graph dashboard" you currently screenshot by hand into a PNG.

Three strategies are supported, in order of preference:

1. `export_with_xlwings` - if you run this on Windows/macOS with a real
   Excel installed, this drives the actual Excel COM/AppleScript API to
   export either a specific Chart object or the visible range of your
   dashboard sheet exactly like a real screenshot. This is the closest to
   what you do manually today and needs no changes to your workbook.

2. `export_with_libreoffice` - if you run this on Linux (e.g. a small
   always-on server that stays connected to the VPN so you don't need to
   do this from your own PC), LibreOffice headless can render the sheet
   to PDF/PNG instead. Requires `soffice` (LibreOffice) to be installed.

3. `export_with_matplotlib` - a fallback that does not touch Excel at all:
   it re-plots the same data (read straight from the workbook) as a
   matplotlib chart. Use this if you'd rather decouple "what Telegram
   gets" from "what my Excel dashboard looks like".

`export_dashboard` tries xlwings, then LibreOffice, then matplotlib, and
returns the path to whichever one succeeded - see main.py.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def export_with_xlwings(excel_path: str, sheet_name: str, out_path: str) -> Path:
    import xlwings as xw  # optional dependency, see requirements-windows.txt

    out_path_obj = Path(out_path)
    out_path_obj.parent.mkdir(parents=True, exist_ok=True)

    app = xw.App(visible=False)
    try:
        wb = app.books.open(excel_path)
        try:
            sheet = wb.sheets[sheet_name]
            if len(sheet.charts) > 0:
                sheet.charts[0].to_png(str(out_path_obj))
            else:
                sheet.used_range.to_png(str(out_path_obj))
        finally:
            wb.close()
    finally:
        app.quit()

    logger.info("Exported dashboard via xlwings -> %s", out_path_obj)
    return out_path_obj


def export_with_libreoffice(excel_path: str, sheet_name: str, out_path: str) -> Path:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise RuntimeError("LibreOffice (soffice) not found on PATH.")

    out_path_obj = Path(out_path)
    out_path_obj.parent.mkdir(parents=True, exist_ok=True)
    out_dir = out_path_obj.parent

    # LibreOffice headless converts the *whole active sheet* to PNG; if your
    # dashboard sheet isn't the first/active one, duplicate the workbook and
    # set it as active before calling this, or export to PDF and crop.
    subprocess.run(
        [soffice, "--headless", "--convert-to", "png", "--outdir", str(out_dir), excel_path],
        check=True,
        timeout=120,
    )

    produced = out_dir / (Path(excel_path).stem + ".png")
    if produced != out_path_obj:
        produced.replace(out_path_obj)

    logger.info("Exported dashboard via LibreOffice -> %s", out_path_obj)
    return out_path_obj


def export_with_matplotlib(
    dates: list,
    series: dict[str, list[float]],
    out_path: str,
    title: str = "Daily FQC Defect Rate",
) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_path_obj = Path(out_path)
    out_path_obj.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 6))
    for label, values in series.items():
        ax.plot(dates, values, marker="o", label=label)

    ax.set_title(title)
    ax.set_xlabel("Date")
    ax.set_ylabel("Defect rate (%)")
    ax.legend()
    ax.grid(True, linestyle="--", alpha=0.4)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_path_obj, dpi=150)
    plt.close(fig)

    logger.info("Exported dashboard via matplotlib -> %s", out_path_obj)
    return out_path_obj


def export_dashboard(
    excel_path: str,
    sheet_name: str,
    out_path: str,
    matplotlib_fallback_data: tuple[list, dict[str, list[float]]] | None = None,
) -> Path:
    """Try xlwings, then LibreOffice, then matplotlib (if fallback data given)."""
    try:
        return export_with_xlwings(excel_path, sheet_name, out_path)
    except Exception as exc:  # noqa: BLE001 - deliberately broad, this is a fallback chain
        logger.warning("xlwings export failed (%s); trying LibreOffice.", exc)

    try:
        return export_with_libreoffice(excel_path, sheet_name, out_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("LibreOffice export failed (%s); trying matplotlib fallback.", exc)

    if matplotlib_fallback_data is not None:
        dates, series = matplotlib_fallback_data
        return export_with_matplotlib(dates, series, out_path)

    raise RuntimeError(
        "All dashboard export strategies failed and no matplotlib fallback data was provided."
    )
