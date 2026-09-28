"""API 호출 모음. 대시보드는 이 모듈로만 API와 통신한다."""

import os
from typing import Any

import requests

API_URL = os.environ.get("API_URL", "http://localhost:8000").rstrip("/")
TIMEOUT_SEC = 10


class ApiError(RuntimeError):
    """API 호출 실패 (연결 실패, 4xx·5xx 응답)."""


def _request(method: str, path: str, **kwargs: Any) -> Any:
    try:
        response = requests.request(
            method, f"{API_URL}{path}", timeout=TIMEOUT_SEC, **kwargs
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ApiError(f"{method} {path} 실패: {exc}") from exc
    return response.json()


def get_health() -> dict[str, Any]:
    return _request("GET", "/health")
