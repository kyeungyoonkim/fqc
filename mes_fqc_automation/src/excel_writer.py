"""Append today's scraped FQC numbers as a new row in the tracking workbook.

Design goals:
  - Never touches existing rows/charts/formulas - only appends one new row.
  - Finds columns by their header text (row 1) rather than hard-coded
    column letters, so re-ordering columns in Excel won't break the script.
  - If the data lives in a real Excel Table (Insert > Table), the table's
    range is auto-extended to include the new row so charts/PivotTables
    that reference the table keep working without any manual resize.
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from src.config import ExcelConfig

logger = logging.getLogger(__name__)


def _find_header_row(ws: Worksheet) -> dict[str, int]:
    """Map header text (row 1) -> 1-indexed column number."""
    headers: dict[str, int] = {}
    for cell in ws[1]:
        if cell.value is not None:
            headers[str(cell.value).strip()] = cell.column
    return headers


def _first_empty_row(ws: Worksheet, date_col: int) -> int:
    row = 2
    while ws.cell(row=row, column=date_col).value not in (None, ""):
        row += 1
    return row


def _extend_table_if_present(ws: Worksheet, table_name: str | None, new_last_row: int) -> None:
    if not table_name:
        return
    table = ws.tables.get(table_name)
    if table is None:
        logger.warning("Excel table %r not found on sheet %r; skipping table resize.", table_name, ws.title)
        return

    start_cell, end_cell = table.ref.split(":")
    start_col_letter = "".join(ch for ch in start_cell if ch.isalpha())
    end_col_letter = "".join(ch for ch in end_cell if ch.isalpha())
    new_ref = f"{start_col_letter}1:{end_col_letter}{new_last_row}"
    table.ref = new_ref
    logger.info("Extended table %r to %s", table_name, new_ref)


def append_daily_row(
    excel_cfg: ExcelConfig,
    row_date: date,
    values: dict[str, float],
) -> Path:
    """Append one row to the tracking workbook.

    `values` keys must match excel_cfg.column_headers keys, e.g.
    {"CTV_E03": 1.23, "CTV_E19": 0.5, ..., "JC_OVERALL": 2.1}
    """
    path = Path(excel_cfg.path)
    if not path.exists():
        raise FileNotFoundError(
            f"Excel file not found at {path}. Update `excel.path` in config.yaml."
        )

    wb = load_workbook(path)
    if excel_cfg.sheet_name not in wb.sheetnames:
        raise ValueError(f"Sheet {excel_cfg.sheet_name!r} not found in {path}.")
    ws = wb[excel_cfg.sheet_name]

    headers = _find_header_row(ws)

    date_col = headers.get(excel_cfg.date_column_header)
    if date_col is None:
        raise ValueError(
            f"Could not find date column header {excel_cfg.date_column_header!r} in row 1 of "
            f"sheet {excel_cfg.sheet_name!r}."
        )

    missing_headers = [
        header
        for key, header in excel_cfg.column_headers.items()
        if header not in headers and key in values
    ]
    if missing_headers:
        raise ValueError(
            f"These column headers from config.yaml were not found in row 1 of the sheet: "
            f"{missing_headers}. Check `excel.column_headers` matches your spreadsheet exactly."
        )

    target_row = _first_empty_row(ws, date_col)
    ws.cell(row=target_row, column=date_col, value=row_date)
    ws.cell(row=target_row, column=date_col).number_format = "yyyy-mm-dd"

    for key, header in excel_cfg.column_headers.items():
        if key not in values:
            continue
        col = headers[header]
        ws.cell(row=target_row, column=col, value=values[key])

    _extend_table_if_present(ws, excel_cfg.table_name, target_row)

    wb.save(path)
    logger.info(
        "Wrote row %d (%s) to %s -> columns %s",
        target_row,
        row_date.isoformat(),
        path,
        ", ".join(get_column_letter(c) for c in sorted(set(headers.values()))),
    )
    return path
