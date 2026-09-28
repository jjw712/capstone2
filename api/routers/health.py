"""GET /health: 서버 상태와 모델 로드 여부."""

from fastapi import APIRouter, Depends

from api.dependencies import ServingState, get_serving_state
from api.schemas import HealthResponse
from roboadvisor import __version__

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health(serving: ServingState = Depends(get_serving_state)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=__version__,
        model_loaded=serving.model_loaded,
        model_version=serving.model_version,
    )
