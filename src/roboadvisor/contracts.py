"""역할 사이에 주고받는 데이터 형식 (관리: A, 변경은 전원 합의).

초안이다. 1주차 회의에서 필드를 확정하고, 바꿀 때는 docs/interfaces.md도 같이 고친다.
예시 데이터는 tests/fixtures/sample_*.json에 있다.

공통 약속 (초안)
- 비중은 0~1 비율이고 합은 1이다. 키는 configs/assets.yaml의 티커를 쓴다.
- as_of는 결정에 쓴 마지막 데이터 날짜다. 그날 종가까지의 정보만 쓴다.
- MDD·VaR·CVaR는 손실 크기를 양수로 적는다 (0.15 = 15% 손실).
"""

from datetime import date, datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

WEIGHT_SUM_TOLERANCE = 1e-4


def check_weights(weights: dict[str, float]) -> None:
    """비중이 0 이상이고 합이 1인지 확인한다."""
    if any(w < 0 for w in weights.values()):
        raise ValueError("비중은 0 이상이어야 합니다 (공매도 금지)")
    total = sum(weights.values())
    if abs(total - 1.0) > WEIGHT_SUM_TOLERANCE:
        raise ValueError(f"비중 합이 1이 아닙니다: {total:.6f}")


class Contract(BaseModel):
    """모든 형식의 부모. 형식에 없는 필드가 오면 조용히 버리지 않고 오류를 낸다."""

    model_config = ConfigDict(extra="forbid")


class Source(Contract):
    """출처. 리서치 결과와 에이전트가 만든 리스크 태그에는 반드시 붙는다."""

    title: str
    url: HttpUrl
    published_at: datetime


class RiskType(StrEnum):
    EARNINGS_SHOCK = "earnings_shock"
    REGULATION_CHANGE = "regulation_change"
    GEOPOLITICAL = "geopolitical"
    PRICE_SWING = "price_swing"
    VOLUME_ANOMALY = "volume_anomaly"


class RiskTag(Contract):
    """D → B·E. 위험 이벤트 한 건."""

    tag_id: str
    ticker: str
    risk_type: RiskType
    severity: float = Field(ge=0, le=1)
    published_at: datetime  # 근거가 공개된 시각. 이보다 이른 결정에는 쓰면 안 된다
    detected_at: datetime  # 태그를 만든 시각
    origin: Literal["agent", "price_proxy"]  # 에이전트 / 가격 기반 대체 태그
    verified: bool = False  # 검증 단계 통과 여부
    sources: list[Source] = Field(default_factory=list)

    @model_validator(mode="after")
    def _agent_tag_needs_source(self) -> Self:
        if self.origin == "agent" and not self.sources:
            raise ValueError("에이전트가 만든 태그에는 출처가 있어야 합니다")
        return self


class MarketInput(Contract):
    """E → B. /optimize 입력. TODO(A·B): 피처 전달 형식 확정."""

    as_of: date
    current_weights: dict[str, float] | None = None

    @model_validator(mode="after")
    def _valid_weights(self) -> Self:
        if self.current_weights is not None:
            check_weights(self.current_weights)
        return self


class ShapFactor(Contract):
    feature: str
    value: float  # 피처 값
    contribution: float  # SHAP 기여도


class Decision(Contract):
    """B·C·D → E. 비중 결정 한 건. 의사결정 이력 DB에 그대로 저장한다."""

    decision_id: str
    as_of: date
    created_at: datetime
    model_version: str  # 서비스 모델의 실험 ID
    model_weights: dict[str, float]  # 모델이 낸 비중
    final_weights: dict[str, float]  # 리스크 규칙 적용 후 비중
    applied_tags: list[str] = Field(default_factory=list)  # RiskTag.tag_id
    applied_rules: list[str] = Field(default_factory=list)
    safeguard_action: str | None = None
    shap_top_factors: list[ShapFactor] = Field(default_factory=list)

    @model_validator(mode="after")
    def _valid_weights(self) -> Self:
        check_weights(self.model_weights)
        check_weights(self.final_weights)
        if set(self.model_weights) != set(self.final_weights):
            raise ValueError("모델 비중과 최종 비중의 자산 목록이 다릅니다")
        return self


class TraceStep(Contract):
    """에이전트의 '현재 생각' 한 줄. 대시보드에 로그로 보여 준다."""

    node: str  # planner / researcher / grader / analyst ...
    message: str
    at: datetime


class ResearchResult(Contract):
    """D → E. 리서치 한 건의 결과."""

    question: str
    answer: str
    citations: list[Source] = Field(min_length=1)  # 명세: 출처 필수
    risk_tags: list[RiskTag] = Field(default_factory=list)
    trace: list[TraceStep] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)


class Period(Contract):
    start: date
    end: date

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.start > self.end:
            raise ValueError("start가 end보다 늦습니다")
        return self


class Metrics(Contract):
    """명세의 12개 지표. 비율은 소수로 적는다 (0.12 = 12%)."""

    cumulative_return: float
    cagr: float
    annual_volatility: float
    var_95: float
    cvar_95: float
    max_drawdown: float
    sharpe: float
    sortino: float
    calmar: float
    alpha: float
    beta: float
    information_ratio: float


class EvaluationResult(Contract):
    """C → E. 전략 하나를 테스트 구간 하나에서 평가한 결과."""

    experiment_id: str
    strategy: Literal["drl", "mvo", "equal_weight", "benchmark"]
    window_id: str
    test_period: Period
    metrics: Metrics


class RunManifest(Contract):
    """B → C·E. artifacts/runs/<실험 ID>/manifest.json 형식.

    모델만 바꾸고 정규화 정보나 자산·피처 순서는 예전 것을 쓰는 실수를 막는다.
    """

    experiment_id: str
    reward: Literal["simple", "sharpe", "mdd_penalty"]
    mdd_lambda: float | None = None  # MDD 페널티 강도 λ, mdd_penalty일 때만
    window_id: str
    train_period: Period
    seed: int
    assets: list[str]  # 학습 때 자산 순서
    features: list[str]  # 학습 때 피처 순서
    total_timesteps: int
    created_at: datetime
    versions: dict[str, str] = Field(default_factory=dict)  # 주요 라이브러리 버전
