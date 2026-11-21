import httpx
import pytest
from asgi_lifespan import LifespanManager

from overcalc_calculation.presentation.main import app_factory


async def test_app_starts_without_database(monkeypatch: pytest.MonkeyPatch) -> None:
    """Startup must not connect: compose races and DB restarts mean 503, not a crash loop."""
    monkeypatch.setenv("OVERCALC_DATABASE_URL", "postgresql+asyncpg://u:p@127.0.0.1:1/x")
    monkeypatch.setenv("OVERCALC_DATABASE_PROBE_TIMEOUT_SECONDS", "0.5")

    app = app_factory()
    async with LifespanManager(app) as manager:
        transport = httpx.ASGITransport(app=manager.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "checks": {"db": "unavailable"}}
