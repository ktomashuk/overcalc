"""E2E suite: runs against a live stack (`make e2e` brings up docker compose)."""

import os

import pytest


@pytest.fixture(scope="session")
def base_url() -> str:
    return os.environ.get("OVERCALC_BASE_URL", "http://localhost:8000")
