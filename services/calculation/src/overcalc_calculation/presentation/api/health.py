from fastapi import APIRouter, Request, Response, status

from overcalc_calculation.presentation.api.schemas import CheckStatus, ReadinessResponse
from overcalc_calculation.presentation.container import Container

router = APIRouter()


@router.get(
    "/health/ready",
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
)
async def ready(request: Request, response: Response) -> ReadinessResponse:
    container: Container = request.app.state.container
    db_ready = await container.readiness_probe.is_ready()
    db: CheckStatus = "ok" if db_ready else "unavailable"
    if not db_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(status=db, checks={"db": db})
