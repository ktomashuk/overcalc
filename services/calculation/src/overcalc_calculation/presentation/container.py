"""Composition root: the only place that decides which adapter implements which port."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine

from overcalc_calculation.application.interfaces.health import ReadinessProbe
from overcalc_calculation.infrastructure.db import create_engine
from overcalc_calculation.infrastructure.health import SqlAlchemyReadinessProbe
from overcalc_calculation.infrastructure.settings import DatabaseSettings


@dataclass(frozen=True, slots=True)
class Container:
    readiness_probe: ReadinessProbe
    engine: AsyncEngine | None = None

    async def aclose(self) -> None:
        if self.engine is not None:
            await self.engine.dispose()


def build_container(settings: DatabaseSettings) -> Container:
    engine = create_engine(settings)
    probe = SqlAlchemyReadinessProbe(engine, timeout_seconds=settings.probe_timeout_seconds)
    return Container(readiness_probe=probe, engine=engine)
