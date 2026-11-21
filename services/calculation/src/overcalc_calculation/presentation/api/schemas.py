"""Public HTTP contract. Deliberately separate from application DTOs."""

from typing import Literal

from pydantic import BaseModel

CheckStatus = Literal["ok", "unavailable"]


class ReadinessResponse(BaseModel):
    status: CheckStatus
    checks: dict[str, CheckStatus]
