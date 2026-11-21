"""In-memory fakes of ports, shared across tests (ARCHITECTURE.md §5)."""


class FakeReadinessProbe:
    def __init__(self, ready: bool = True) -> None:
        self.ready = ready

    async def is_ready(self) -> bool:
        return self.ready
