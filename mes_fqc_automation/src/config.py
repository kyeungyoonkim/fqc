"""Load and validate config.yaml + .env for the MES FQC automation."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

METRIC_KEYS = ("E03", "E19", "T11", "OVERALL")


@dataclass
class MetricSelector:
    selector: str
    selector_type: str = "css"  # "css" or "xpath"
    regex: str | None = None


@dataclass
class LoginConfig:
    url: str
    username_selector: str
    password_selector: str
    submit_selector: str
    username_env: str
    password_env: str
    success_selector: str | None = None


@dataclass
class FqcPageConfig:
    url: str
    navigation_steps: list[str] = field(default_factory=list)
    wait_for_selector: str | None = None


@dataclass
class SiteConfig:
    name: str
    enabled: bool
    requires_vpn: bool
    base_url: str
    login: LoginConfig
    fqc_page: FqcPageConfig
    metrics: dict[str, MetricSelector]

    def credentials(self) -> tuple[str, str]:
        username = os.environ.get(self.login.username_env, "")
        password = os.environ.get(self.login.password_env, "")
        if not username or not password:
            raise RuntimeError(
                f"[{self.name}] Missing credentials. Set {self.login.username_env} "
                f"and {self.login.password_env} in your .env file."
            )
        return username, password


@dataclass
class ExcelConfig:
    path: str
    sheet_name: str
    table_name: str | None
    date_column_header: str
    column_headers: dict[str, str]
    dashboard_sheet_name: str | None = None


@dataclass
class TelegramConfig:
    bot_token_env: str
    chat_id_env: str
    caption_template: str

    def bot_token(self) -> str:
        token = os.environ.get(self.bot_token_env, "")
        if not token:
            raise RuntimeError(f"Missing {self.bot_token_env} in your .env file.")
        return token

    def chat_id(self) -> str:
        chat_id = os.environ.get(self.chat_id_env, "")
        if not chat_id:
            raise RuntimeError(f"Missing {self.chat_id_env} in your .env file.")
        return chat_id


@dataclass
class OutputConfig:
    chart_image_path: str
    log_dir: str


@dataclass
class AppConfig:
    sites: dict[str, SiteConfig]
    excel: ExcelConfig
    telegram: TelegramConfig
    output: OutputConfig


def _build_site_config(name: str, raw: dict[str, Any]) -> SiteConfig:
    login_raw = raw["login"]
    fqc_raw = raw["fqc_page"]
    metrics_raw = raw["metrics"]

    metrics = {
        key: MetricSelector(
            selector=m["selector"],
            selector_type=m.get("selector_type", "css"),
            regex=m.get("regex"),
        )
        for key, m in metrics_raw.items()
    }
    missing = [k for k in METRIC_KEYS if k not in metrics]
    if missing:
        raise ValueError(f"[{name}] config.yaml is missing metrics: {missing}")

    return SiteConfig(
        name=name,
        enabled=raw.get("enabled", True),
        requires_vpn=raw.get("requires_vpn", False),
        base_url=raw["base_url"],
        login=LoginConfig(
            url=login_raw["url"],
            username_selector=login_raw["username_selector"],
            password_selector=login_raw["password_selector"],
            submit_selector=login_raw["submit_selector"],
            username_env=login_raw["username_env"],
            password_env=login_raw["password_env"],
            success_selector=login_raw.get("success_selector"),
        ),
        fqc_page=FqcPageConfig(
            url=fqc_raw.get("url", ""),
            navigation_steps=fqc_raw.get("navigation_steps", []) or [],
            wait_for_selector=fqc_raw.get("wait_for_selector"),
        ),
        metrics=metrics,
    )


def load_config(config_path: str | Path = "config.yaml", env_path: str | Path | None = None) -> AppConfig:
    """Load config.yaml (site/excel/telegram settings) and .env (secrets)."""
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(
            f"{config_path} not found. Copy config.example.yaml to {config_path.name} "
            "and fill in your real MES/Excel/Telegram settings first."
        )

    load_dotenv(dotenv_path=env_path or (config_path.parent / ".env"))

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    sites = {name: _build_site_config(name, site_raw) for name, site_raw in raw["sites"].items()}

    excel_raw = raw["excel"]
    excel = ExcelConfig(
        path=excel_raw["path"],
        sheet_name=excel_raw["sheet_name"],
        table_name=excel_raw.get("table_name"),
        date_column_header=excel_raw["date_column_header"],
        column_headers=excel_raw["column_headers"],
        dashboard_sheet_name=excel_raw.get("dashboard_sheet_name"),
    )

    telegram_raw = raw["telegram"]
    telegram = TelegramConfig(
        bot_token_env=telegram_raw["bot_token_env"],
        chat_id_env=telegram_raw["chat_id_env"],
        caption_template=telegram_raw.get("caption_template", "Daily FQC Report - {date}"),
    )

    output_raw = raw.get("output", {})
    output = OutputConfig(
        chart_image_path=output_raw.get("chart_image_path", "./output/daily_fqc_dashboard.png"),
        log_dir=output_raw.get("log_dir", "./output/logs"),
    )

    return AppConfig(sites=sites, excel=excel, telegram=telegram, output=output)
