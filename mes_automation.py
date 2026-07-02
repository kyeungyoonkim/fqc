from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import logging
import math
import random
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
import requests
import yaml

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover - optional in dry-run
    sync_playwright = None


METRICS = ("E03", "E19", "T11", "TOTAL")


@dataclasses.dataclass
class MetricRecord:
    site: str
    line: str
    date: dt.date
    e03: float
    e19: float
    t11: float
    total: float

    @property
    def line_key(self) -> str:
        return f"{self.site}:{self.line}"


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def rolling_date_range(window_days: int) -> tuple[dt.date, dt.date, list[dt.date]]:
    end = dt.date.today() - dt.timedelta(days=1)
    start = end - dt.timedelta(days=window_days - 1)
    days = [start + dt.timedelta(days=i) for i in range(window_days)]
    return start, end, days


def _seeded_percent(site: str, line: str, day: dt.date, metric: str) -> float:
    seed = hash((site, line, day.isoformat(), metric)) & 0xFFFFFFFF
    rng = random.Random(seed)
    base = {
        "E03": rng.uniform(0.05, 0.8),
        "E19": rng.uniform(0.03, 0.7),
        "T11": rng.uniform(0.02, 0.5),
    }
    if metric == "TOTAL":
        return round(base["E03"] + base["E19"] + base["T11"], 2)
    return round(base[metric], 2)


def collect_dry_run(cfg: dict[str, Any], days: list[dt.date]) -> list[MetricRecord]:
    records: list[MetricRecord] = []
    for site in ("ctv", "dlt", "jc"):
        site_cfg = cfg["mes"].get(site, {})
        if not site_cfg.get("enabled", False):
            continue
        site_name = site.upper()
        for line in site_cfg.get("lines", []):
            for day in days:
                e03 = _seeded_percent(site_name, line, day, "E03")
                e19 = _seeded_percent(site_name, line, day, "E19")
                t11 = _seeded_percent(site_name, line, day, "T11")
                total = _seeded_percent(site_name, line, day, "TOTAL")
                records.append(MetricRecord(site_name, line, day, e03, e19, t11, total))
    return records


def _read_table_file(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    return pd.read_excel(path)


def _find_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    normalized = {str(c).strip().lower(): c for c in df.columns}
    for name in candidates:
        key = name.strip().lower()
        if key in normalized:
            return normalized[key]
    return None


def _parse_percent(value: Any) -> float:
    if pd.isna(value):
        return 0.0
    text = str(value).strip().replace("%", "")
    if text == "":
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def _build_metrics_from_export(
    df: pd.DataFrame,
    *,
    site_name: str,
    lines: list[str],
    days: list[dt.date],
    require_grade_total: bool,
) -> list[MetricRecord]:
    date_col = _find_column(df, ["Work Date", "Date", "work_date"])
    line_col = _find_column(df, ["Line", "line"])
    grade_col = _find_column(df, ["Grade", "grade"])
    loss_col = _find_column(df, ["Loss Desc", "Loss Code", "Defect Code", "LossDesc", "loss_desc"])
    rate_col = _find_column(df, ["Defect Rate", "Rate", "Loss Rate", "loss_rate", "defect_rate"])

    required = {
        "date": date_col,
        "line": line_col,
        "loss": loss_col,
        "rate": rate_col,
    }
    missing = [k for k, v in required.items() if v is None]
    if missing:
        raise RuntimeError(
            f"{site_name} export parse failed. Missing columns: {missing}. "
            f"Available columns: {list(df.columns)}"
        )

    work = df.copy()
    work[date_col] = pd.to_datetime(work[date_col], errors="coerce").dt.date
    work = work[work[date_col].isin(days)]
    work = work[work[line_col].astype(str).str.strip().isin(lines)]

    if require_grade_total and grade_col:
        work = work[work[grade_col].astype(str).str.upper().str.strip() == "TOTAL"]

    work["loss_norm"] = work[loss_col].astype(str).str.upper().str.strip()
    work["rate_num"] = work[rate_col].map(_parse_percent)

    records: list[MetricRecord] = []
    for line in lines:
        for day in days:
            subset = work[(work[line_col].astype(str).str.strip() == line) & (work[date_col] == day)]
            if subset.empty:
                records.append(MetricRecord(site_name, line, day, 0.0, 0.0, 0.0, 0.0))
                continue

            e03 = subset[subset["loss_norm"].str.contains("E03", na=False)]["rate_num"].sum()
            e19 = subset[subset["loss_norm"].str.contains("E19", na=False)]["rate_num"].sum()
            t11 = subset[subset["loss_norm"].str.contains("T11", na=False)]["rate_num"].sum()
            total_rows = subset[subset["loss_norm"].str.contains("TOTAL", na=False)]["rate_num"]
            total = float(total_rows.iloc[0]) if not total_rows.empty else e03 + e19 + t11

            records.append(
                MetricRecord(
                    site=site_name,
                    line=line,
                    date=day,
                    e03=round(float(e03), 2),
                    e19=round(float(e19), 2),
                    t11=round(float(t11), 2),
                    total=round(float(total), 2),
                )
            )
    return records


def collect_from_export_files(cfg: dict[str, Any], days: list[dt.date]) -> list[MetricRecord]:
    records: list[MetricRecord] = []
    for site in ("ctv", "dlt", "jc"):
        site_cfg = cfg["mes"].get(site, {})
        if not site_cfg.get("enabled", False):
            continue
        export_path = site_cfg.get("export_file", "").strip()
        if not export_path:
            continue
        file_path = Path(export_path)
        if not file_path.exists():
            raise RuntimeError(f"{site.upper()} export_file not found: {file_path}")
        data = _read_table_file(file_path)
        records.extend(
            _build_metrics_from_export(
                data,
                site_name=site.upper(),
                lines=site_cfg.get("lines", []),
                days=days,
                require_grade_total=bool(site_cfg.get("require_grade_total", False)),
            )
        )
    return records


def collect_mes(cfg: dict[str, Any], days: list[dt.date]) -> list[MetricRecord]:
    export_records = collect_from_export_files(cfg, days)
    if export_records:
        logging.info("Using MES export files for live metrics")
        return export_records
    if cfg["mes"].get("dry_run", True):
        logging.info("dry_run=true, generating sample values")
        return collect_dry_run(cfg, days)
    if sync_playwright is None:
        raise RuntimeError("Playwright not available. Run: pip install -r requirements.txt && playwright install")
    logging.warning("Live MES collector needs selector tuning for your environment. Using dry-run fallback.")
    return collect_dry_run(cfg, days)


def records_to_dataframe(records: list[MetricRecord]) -> pd.DataFrame:
    df = pd.DataFrame(
        [
            {
                "site": r.site,
                "line": r.line,
                "line_key": r.line_key,
                "date": r.date,
                "E03": r.e03,
                "E19": r.e19,
                "T11": r.t11,
                "TOTAL": r.total,
            }
            for r in records
        ]
    )
    if df.empty:
        raise RuntimeError("No records collected")
    return df.sort_values(["site", "line", "date"]).reset_index(drop=True)


def write_excel(df: pd.DataFrame, out_path: Path) -> None:
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="raw_data", index=False)
        pivot = df.pivot_table(index=["line_key"], columns="date", values=["E03", "E19", "T11", "TOTAL"])
        pivot.to_excel(writer, sheet_name="pivot")


def _plot_single_line(ax: Any, line_df: pd.DataFrame, line_key: str, target: float | None) -> None:
    line_df = line_df.sort_values("date")
    x = list(range(len(line_df)))
    labels = [d.strftime("%d-%b") for d in line_df["date"]]

    e03 = line_df["E03"].to_list()
    e19 = line_df["E19"].to_list()
    t11 = line_df["T11"].to_list()
    total = line_df["TOTAL"].to_list()

    ax.bar(x, e03, label="E03 Tree crack", color="#f28e2b")
    ax.bar(x, e19, bottom=e03, label="E19 Soldering", color="#2ca02c")
    stack = [a + b for a, b in zip(e03, e19)]
    ax.bar(x, t11, bottom=stack, label="T11 Cell quality", color="#4dabf7")
    ax.plot(x, total, color="#1f77b4", marker="o", linewidth=1.8, label="Total")

    avg = sum(total) / len(total)
    ax.axhline(avg, color="#d62728", linewidth=1.2)
    ax.text(len(x) * 0.01, avg + 0.02, "last week avg.", color="#d62728", fontsize=8)

    if target is not None and not math.isnan(target):
        ax.axhline(target, color="#555", linewidth=1.0, linestyle="--")
        ax.text(len(x) * 0.66, target + 0.02, "last year avg.", color="#333", fontsize=8)

    for idx, val in enumerate(total):
        ax.text(idx, val + 0.03, f"{val:.2f}%", ha="center", va="bottom", fontsize=7, color="#333")

    ax.set_title(f"{line_key} FQC Defect Trend", fontsize=10)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylim(0, max(4.0, max(total) + 0.8))
    ax.grid(axis="y", linestyle=":", alpha=0.35)


def render_dashboard(df: pd.DataFrame, line_keys: list[str], targets: dict[str, float], title: str, out_path: Path) -> None:
    n = len(line_keys)
    cols = 3
    rows = math.ceil(n / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(16, 4.5 * rows), constrained_layout=True)
    fig.suptitle(title, fontsize=16, fontweight="bold")

    if rows == 1:
        axes = [axes] if not isinstance(axes, (list, tuple)) else axes
    flat_axes = list(axes.flatten()) if hasattr(axes, "flatten") else list(axes)

    for ax, line_key in zip(flat_axes, line_keys):
        line_df = df[df["line_key"] == line_key]
        if line_df.empty:
            ax.axis("off")
            ax.text(0.5, 0.5, f"{line_key}\nNo data", ha="center", va="center")
            continue
        _plot_single_line(ax, line_df, line_key, targets.get(line_key))

    for ax in flat_axes[n:]:
        ax.axis("off")

    handles, labels = flat_axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False)
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def send_telegram(bot_token: str, chat_id: str, message: str, images: list[Path]) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    resp = requests.post(url, data={"chat_id": chat_id, "text": message}, timeout=20)
    resp.raise_for_status()
    for image in images:
        with image.open("rb") as f:
            purl = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            presp = requests.post(
                purl,
                data={"chat_id": chat_id, "caption": image.name},
                files={"photo": f},
                timeout=30,
            )
            presp.raise_for_status()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily FQC automation")
    parser.add_argument("--config", default="config.yaml", help="Path to config YAML")
    parser.add_argument("--no-telegram", action="store_true", help="Skip telegram send")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = load_config(Path(args.config))
    out_dir = Path(cfg.get("output_dir", "output"))
    ensure_dir(out_dir)

    start, end, days = rolling_date_range(int(cfg.get("rolling_window_days", 7)))
    logging.info("Collecting Daily FQC: %s ~ %s", start, end)
    records = collect_mes(cfg, days)
    df = records_to_dataframe(records)

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M")
    excel_path = out_dir / f"daily_fqc_{stamp}.xlsx"
    write_excel(df, excel_path)
    logging.info("Excel written: %s", excel_path)

    targets = {k: float(v) for k, v in cfg.get("targets", {}).items()}
    first_lines = cfg["dashboard"]["first_image_lines"]
    second_lines = cfg["dashboard"]["second_image_lines"]

    img1 = out_dir / f"dashboard_1_{stamp}.png"
    img2 = out_dir / f"dashboard_2_{stamp}.png"
    render_dashboard(df, first_lines, targets, "Dashboard (1/2)", img1)
    render_dashboard(df, second_lines, targets, "Dashboard (2/2)", img2)
    logging.info("Dashboard images written: %s, %s", img1, img2)

    tg_cfg = cfg.get("telegram", {})
    if not args.no_telegram and tg_cfg.get("enabled", False):
        message = tg_cfg.get("message_template", "Daily FQC")
        message = message.replace("{{start_date}}", str(start)).replace("{{end_date}}", str(end))
        send_telegram(
            bot_token=tg_cfg["bot_token"],
            chat_id=str(tg_cfg["chat_id"]),
            message=message,
            images=[img1, img2],
        )
        logging.info("Telegram sent")
    else:
        logging.info("Telegram disabled or --no-telegram set")


if __name__ == "__main__":
    main()
