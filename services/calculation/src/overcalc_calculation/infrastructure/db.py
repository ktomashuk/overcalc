from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from overcalc_calculation.infrastructure.settings import DatabaseSettings


def create_engine(settings: DatabaseSettings) -> AsyncEngine:
    """Build the engine. Connects lazily: nothing touches the network until first use."""
    return create_async_engine(settings.url, pool_pre_ping=True)
