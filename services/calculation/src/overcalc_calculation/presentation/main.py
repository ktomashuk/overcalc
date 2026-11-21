"""ASGI entry point: `uvicorn overcalc_calculation.presentation.main:app_factory --factory`."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from overcalc_calculation.infrastructure.settings import DatabaseSettings
from overcalc_calculation.presentation.api import health
from overcalc_calculation.presentation.container import Container, build_container


def create_app(container: Container) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        # No DB work on startup: the app must boot while Postgres is still down.
        yield
        await container.aclose()

    app = FastAPI(title="Overcalc calculation", lifespan=lifespan)
    app.state.container = container
    app.include_router(health.router)
    return app


def app_factory() -> FastAPI:
    return create_app(build_container(DatabaseSettings()))
