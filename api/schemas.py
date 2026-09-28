"""HTTP 요청·응답 형식. contracts.py와 겹치는 형식은 새로 만들지 않고 재사용한다."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    version: str
    model_loaded: bool
    model_version: str | None = None
