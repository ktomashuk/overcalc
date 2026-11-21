import httpx

from overcalc_calculation.presentation.container import Container
from overcalc_calculation.presentation.main import create_app
from tests.fakes import FakeReadinessProbe


async def _get_ready(probe: FakeReadinessProbe) -> httpx.Response:
    app = create_app(Container(readiness_probe=probe))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get("/health/ready")


async def test_ready_returns_200_when_db_ok() -> None:
    response = await _get_ready(FakeReadinessProbe(ready=True))

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"db": "ok"}}


async def test_ready_returns_503_when_db_unavailable() -> None:
    response = await _get_ready(FakeReadinessProbe(ready=False))

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "checks": {"db": "unavailable"}}
