import pytest

from overcalc_calculation.infrastructure.settings import DatabaseSettings


def test_settings_read_url_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    url = "postgresql+asyncpg://user:secret@db.example:5432/calculation"
    monkeypatch.setenv("OVERCALC_DATABASE_URL", url)

    settings = DatabaseSettings()

    assert settings.url == url
    assert settings.probe_timeout_seconds == 2.0
