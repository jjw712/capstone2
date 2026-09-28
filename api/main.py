"""FastAPI 앱. 저장소 루트에서 실행: uvicorn api.main:app --reload"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.dependencies import load_serving_state
from api.routers import health
from roboadvisor import DISCLAIMER, __version__


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 모델은 서버 시작 때 한 번만 준비한다 (요청마다 로드하면 5초 기준을 넘기기 쉽다)
    app.state.serving = load_serving_state()
    yield


app = FastAPI(
    title="Robo-Advisor API",
    version=__version__,
    description=f"에이전틱 RAG + 강화학습 통합 로보어드바이저 API.\n\n{DISCLAIMER}",
    lifespan=lifespan,
)
app.include_router(health.router)
