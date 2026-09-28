# 인터페이스 (초안)

역할 사이에 주고받는 데이터 형식. 코드 정의는 `src/roboadvisor/contracts.py`이고, 이 문서는 설명이다. 한쪽을 바꾸면 다른 쪽도 같이 고친다.

## 공통 약속

1주차 회의에서 확정한다.

| 항목 | 초안 |
|---|---|
| 자산 순서 | `configs/assets.yaml` 순서. 배열은 이 순서를 따르고, JSON에서는 `{티커: 값}`으로 쓴다 |
| 비중 | 0~1 비율, 합 1, 공매도 없음 |
| 기준일 `as_of` | 결정에 쓴 마지막 데이터 날짜. 그날 종가까지의 정보만 쓴다 |
| 체결 시점 | TODO: 기준일 종가 / 다음 거래일 |
| 손실 지표 부호 | MDD·VaR·CVaR는 손실 크기를 양수로 (0.15 = 15% 손실) |
| 시각 | ISO 8601, 한국 시간(+09:00) |

## 형식

| 형식 | 코드 | 만드는 사람 → 쓰는 사람 | 담는 정보 |
|---|---|---|---|
| 전처리 데이터 | parquet (TODO: 열 구성) | A → B·C | 날짜 × 자산 × 피처 |
| 시장 입력 | `MarketInput` | E → B | 기준일, 현재 비중 (TODO: 피처 전달 방식) |
| 리스크 태그 | `RiskTag` | D → B·E | 자산, 위험 유형, 심각도, 공개·탐지 시각, 출처, 검증 여부 |
| 비중 결정 | `Decision` | B·C·D → E | 결정 ID, 모델 비중, 최종 비중, 적용 태그·규칙, 모델 버전, SHAP 상위 요인 |
| 리서치 결과 | `ResearchResult` | D → E | 질문, 답변, 출처(1개 이상), 리스크 태그, 단계별 생각 |
| 평가 결과 | `EvaluationResult` | C → E | 실험 ID, 전략, 테스트 기간, 12개 지표 |
| 모델 묶음 정보 | `RunManifest` | B → C·E | 실험 ID, 보상·λ, 기간, 자산·피처 순서, 시드, 버전 |

예시는 `tests/fixtures/sample_*.json`에 있고, `tests/unit/test_contracts.py`가 예시가 형식에 맞는지 확인한다. 형식에 없는 필드가 오면 조용히 무시하지 않고 오류를 낸다.

ANOVA 입력(전략별 기간 수익률)은 `artifacts/runs/<실험 ID>/portfolio_history.parquet`에서 읽는다.

## 아직 정할 것

1주차 회의 안건. 추천안은 출발점일 뿐이고, 정해지면 위 표와 `contracts.py`에 옮긴다.

| 항목 | 정할 사람 | 추천안 |
|---|---|---|
| 체결 시점 | B·C | 기준일 종가로 결정하고 다음 거래일에 체결. 같은 날 종가에 체결하면 결정에 쓴 가격으로 바로 거래하는 셈이라 성과가 부풀려질 수 있다 |
| 전처리 parquet 열 구성 | A·B·C | A가 1주차에 예시 파일로 제안 |
| `MarketInput` 피처 전달 방식 | A·B·E | 기준일과, 선택적으로 최근 가격을 받는다. 피처는 서버가 학습 때와 같은 전처리로 만든다. 동료 평가가 "`POST /optimize`에 현재 시장 데이터 전송"으로 확인하기 때문 |
| 리스크 태그 저장 위치 | D·B·E | `storage` DB의 `risk_tags` 테이블. 결정 기록이 태그 ID를 가리키고, 서비스와 백테스트가 같은 곳에서 읽는다. 가격 기반 대체 태그도 `origin=price_proxy`로 같은 테이블에 둔다 |
| `artifacts/serving/` 파일 구성 | B·C·E | 아래 구조 |
| ANOVA 표본 단위 | C | 시드별 성과를 쓰면 시드 수가 곧 B의 학습량이다. MVO·동일가중은 시드가 없어서 검증 2는 월별 수익률 같은 기간 단위 표본이 필요하다 (`configs/evaluation.yaml`의 `sample_unit`) |

```
artifacts/serving/
├── model/              고른 실험의 runs/<실험 ID>/ 묶음 (manifest.json 포함)
├── evaluations.json    EvaluationResult 목록 → GET /backtest
├── anova.json          ANOVA 3종 결과 (F·p·η²·Tukey) → 대시보드 ANOVA 탭
└── shap/               주요 결정의 SHAP 값 → POST /explain
```
