"""설정 로더 (관리: E). 모든 코드는 설정값을 여기서 읽는다.

- 실험·모델 설정: configs/*.yaml → load_config("rl")
- 비밀 값·실행 경로: .env 또는 환경 변수 → get_settings()
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

# 저장소 루트. Docker처럼 위치가 다르면 PROJECT_ROOT 환경 변수로 지정한다.
PROJECT_ROOT = Path(
    os.environ.get("PROJECT_ROOT") or Path(__file__).resolve().parents[2]
)
CONFIG_DIR = PROJECT_ROOT / "configs"


class Settings(BaseSettings):
    """환경 변수와 .env 값. 변수 이름은 대문자로 쓴다 (예: OPENAI_API_KEY)."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", extra="ignore", env_ignore_empty=True
    )

    openai_api_key: str | None = None
    dart_api_key: str | None = None
    data_dir: Path = PROJECT_ROOT / "data"
    artifacts_dir: Path = PROJECT_ROOT / "artifacts"
    database_url: str = (
        "sqlite:///" + (PROJECT_ROOT / "data" / "app" / "app.db").as_posix()
    )

    @property
    def serving_dir(self) -> Path:
        """API가 읽는 모델·결과 묶음 위치."""
        return self.artifacts_dir / "serving"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def load_config(name: str) -> dict[str, Any]:
    """configs/<name>.yaml을 읽는다. 예: load_config("trading")["costs"]["fee_rate"]"""
    path = CONFIG_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"설정 파일이 없습니다: {path}")
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
