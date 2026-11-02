import pytest

from bot import config


def test_validate_reports_every_missing_setting(monkeypatch):
    monkeypatch.setattr(config, "DISCORD_TOKEN", "")
    monkeypatch.setattr(config, "GUILD_ID", 0)
    monkeypatch.setattr(config, "SHEET_ID", "")
    with pytest.raises(RuntimeError) as exc:
        config.validate()
    message = str(exc.value)
    assert "DISCORD_TOKEN" in message and "GUILD_ID" in message and "SHEET_ID" in message


def test_validate_passes_when_everything_is_set(monkeypatch):
    monkeypatch.setattr(config, "DISCORD_TOKEN", "token")
    monkeypatch.setattr(config, "GUILD_ID", 123)
    monkeypatch.setattr(config, "SHEET_ID", "sheet")
    config.validate()  # must not raise
