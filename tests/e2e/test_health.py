import httpx


def test_ready_reports_db_ok(base_url: str) -> None:
    response = httpx.get(f"{base_url}/health/ready", timeout=5.0)

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"db": "ok"}}
