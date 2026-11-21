from typing import Protocol


class ReadinessProbe(Protocol):
    """Can the service reach what it needs to serve requests?

    Contract: never raises, and answers within the adapter's own timeout.
    """

    async def is_ready(self) -> bool: ...
