"""ReadinessProbe contract: one suite, run against the fake and the real adapter.

Contract: `is_ready()` never raises, and it answers within the adapter's timeout.
"""

import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AsyncExitStack

import pytest

from overcalc_calculation.application.interfaces.health import ReadinessProbe
from overcalc_calculation.infrastructure.db import create_engine
from overcalc_calculation.infrastructure.health import SqlAlchemyReadinessProbe
from overcalc_calculation.infrastructure.settings import DatabaseSettings
from tests.fakes import FakeReadinessProbe

# Nothing listens on port 1: connection refused right away.
DOWN_URL = "postgresql+asyncpg://u:p@127.0.0.1:1/x"
# Non-routable address: the connect attempt hangs until something gives up.
BLACKHOLE_URL = "postgresql+asyncpg://u:p@10.255.255.1:5432/x"
BLACKHOLE_TIMEOUT_SECONDS = 0.5

ProbeFactory = Callable[[str, float], Awaitable[ReadinessProbe]]


@pytest.fixture(params=["fake", pytest.param("sqlalchemy", marks=pytest.mark.integration)])
async def make_probe(request: pytest.FixtureRequest) -> AsyncIterator[ProbeFactory]:
    """Build a probe for a backend URL. The fake is "ready" only for the real Postgres URL."""
    async with AsyncExitStack() as stack:

        async def factory(url: str, timeout_seconds: float) -> ReadinessProbe:
            if request.param == "fake":
                return FakeReadinessProbe(ready=url == "postgres-up")
            engine = create_engine(DatabaseSettings(url=url, probe_timeout_seconds=timeout_seconds))
            stack.push_async_callback(engine.dispose)
            return SqlAlchemyReadinessProbe(engine, timeout_seconds=timeout_seconds)

        yield factory


@pytest.fixture
async def ready_probe(request: pytest.FixtureRequest, make_probe: ProbeFactory) -> ReadinessProbe:
    is_fake = request.node.callspec.params["make_probe"] == "fake"
    url = "postgres-up" if is_fake else request.getfixturevalue("postgres_url")
    return await make_probe(url, 2.0)


@pytest.fixture
async def down_probe(make_probe: ProbeFactory) -> ReadinessProbe:
    return await make_probe(DOWN_URL, 2.0)


@pytest.fixture
async def blackhole_probe(make_probe: ProbeFactory) -> ReadinessProbe:
    return await make_probe(BLACKHOLE_URL, BLACKHOLE_TIMEOUT_SECONDS)


async def test_ready_when_backend_up(ready_probe: ReadinessProbe) -> None:
    assert await ready_probe.is_ready() is True


async def test_not_ready_when_backend_down(down_probe: ReadinessProbe) -> None:
    assert await down_probe.is_ready() is False


async def test_not_ready_answer_is_bounded(blackhole_probe: ReadinessProbe) -> None:
    started = time.monotonic()

    ready = await blackhole_probe.is_ready()

    assert ready is False
    assert time.monotonic() - started < 1.5
