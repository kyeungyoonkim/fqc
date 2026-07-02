from pathlib import Path

from src.config import TelegramConfig
from src.telegram_sender import send_message, send_photo


class FakeResponse:
    def __init__(self, json_data):
        self._json_data = json_data

    def raise_for_status(self):
        pass

    def json(self):
        return self._json_data


def _telegram_cfg(monkeypatch) -> TelegramConfig:
    monkeypatch.setenv("TG_TOKEN", "fake-token")
    monkeypatch.setenv("TG_CHAT", "999")
    return TelegramConfig(
        bot_token_env="TG_TOKEN",
        chat_id_env="TG_CHAT",
        caption_template="Report for {date}",
    )


def test_send_photo_posts_expected_payload(tmp_path, monkeypatch):
    cfg = _telegram_cfg(monkeypatch)
    image_path = tmp_path / "chart.png"
    image_path.write_bytes(b"fake-png-bytes")

    captured = {}

    def fake_post(url, data=None, files=None, timeout=None):
        captured["url"] = url
        captured["data"] = data
        captured["has_photo"] = "photo" in files
        return FakeResponse({"ok": True})

    monkeypatch.setattr("src.telegram_sender.requests.post", fake_post)

    send_photo(cfg, image_path, "hello")

    assert captured["url"] == "https://api.telegram.org/botfake-token/sendPhoto"
    assert captured["data"] == {"chat_id": "999", "caption": "hello"}
    assert captured["has_photo"] is True


def test_send_message_posts_expected_payload(monkeypatch):
    cfg = _telegram_cfg(monkeypatch)
    captured = {}

    def fake_post(url, data=None, timeout=None):
        captured["url"] = url
        captured["data"] = data
        return FakeResponse({"ok": True})

    monkeypatch.setattr("src.telegram_sender.requests.post", fake_post)

    send_message(cfg, "some alert text")

    assert captured["url"] == "https://api.telegram.org/botfake-token/sendMessage"
    assert captured["data"] == {"chat_id": "999", "text": "some alert text"}


def test_send_photo_raises_when_telegram_reports_not_ok(tmp_path, monkeypatch):
    cfg = _telegram_cfg(monkeypatch)
    image_path = tmp_path / "chart.png"
    image_path.write_bytes(b"fake-png-bytes")

    monkeypatch.setattr(
        "src.telegram_sender.requests.post",
        lambda *a, **k: FakeResponse({"ok": False, "description": "bad token"}),
    )

    try:
        send_photo(cfg, image_path, "hello")
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "bad token" in str(exc)
