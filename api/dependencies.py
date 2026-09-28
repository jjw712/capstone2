"""실행 자원 준비. 서버가 시작할 때 한 번 만들고 요청마다 꺼내 쓴다."""

import json
from dataclasses import dataclass

from fastapi import Request

from roboadvisor.config import get_settings


@dataclass
class ServingState:
    model_loaded: bool = False
    model_version: str | None = None


def load_serving_state() -> ServingState:
    """artifacts/serving/의 모델 묶음 정보를 읽는다.

    TODO(B·E): rl.model_bundle로 실제 모델을 로드하고 model_loaded를 True로 바꾼다.
    """
    manifest = get_settings().serving_dir / "manifest.json"
    if not manifest.exists():
        return ServingState()
    info = json.loads(manifest.read_text(encoding="utf-8"))
    return ServingState(model_version=info.get("experiment_id"))


def get_serving_state(request: Request) -> ServingState:
    return request.app.state.serving
