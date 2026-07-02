import shutil
from pathlib import Path

from src.config import METRIC_KEYS, load_config

EXAMPLE_CONFIG = Path(__file__).resolve().parent.parent / "config.example.yaml"


def test_load_config_example(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yaml"
    shutil.copy(EXAMPLE_CONFIG, config_path)

    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "CTV_USERNAME=ctv_user",
                "CTV_PASSWORD=ctv_pass",
                "DLT_USERNAME=dlt_user",
                "DLT_PASSWORD=dlt_pass",
                "JC_USERNAME=jc_user",
                "JC_PASSWORD=jc_pass",
                "TELEGRAM_BOT_TOKEN=dummy-token",
                "TELEGRAM_CHAT_ID=12345",
            ]
        ),
        encoding="utf-8",
    )

    cfg = load_config(config_path, env_path=env_path)

    assert set(cfg.sites.keys()) == {"CTV", "DLT", "JC"}
    assert cfg.sites["DLT"].requires_vpn is True
    assert cfg.sites["CTV"].requires_vpn is False

    for site in cfg.sites.values():
        for key in METRIC_KEYS:
            assert key in site.metrics

    assert cfg.sites["CTV"].credentials() == ("ctv_user", "ctv_pass")
    assert cfg.telegram.bot_token() == "dummy-token"
    assert cfg.telegram.chat_id() == "12345"

    assert cfg.excel.column_headers["CTV_E03"] == "CTV E03"
    assert cfg.excel.dashboard_sheet_name == "Dashboard"


def test_load_config_missing_file_raises(tmp_path):
    missing_path = tmp_path / "does_not_exist.yaml"
    try:
        load_config(missing_path)
        assert False, "expected FileNotFoundError"
    except FileNotFoundError:
        pass
