# evaluation/ (C 설명·평가)

실험을 돌리고 결과를 비교·해석한다. 설정은 `configs/evaluation.yaml`, `configs/experiments.yaml`.

- `input_data.py`: A의 `data/processed/` parquet 4종을 읽고 열·자산 순서·거래일 일치를 확인한다. `EvaluationData.test_window("w1")`로 설정된 테스트 기간만 선택한다
- `walk_forward.py`: 기간마다 B의 학습 함수 → 평가 순서로 실행. 같은 실험 ID 결과가 이미 있으면 학습을 건너뛴다
- `backtest.py`: DRL·MVO·동일가중·벤치마크를 같은 조건으로 평가 (`trading_env/accounting.py`, `rl/policy.py` 사용)
- `metrics.py`: 12개 지표 (A가 구현, C가 사용)
- `statistics.py`: ANOVA 3종·Tukey HSD·η²
- `explain.py`: SHAP Summary·Force Plot

실험 결과는 `artifacts/runs/`에, 제출용으로 고른 그림·표는 `reports/`에 둔다.
B → C 출력 형식은 [미합의 제안안](b_to_c_proposal.md)에 정리했다.
A·B·E와 결정할 사항은 [연동 합의 안건](integration_agreements.md)에 모았다.

현재 A가 내보내는 파일은 `returns.parquet`(자산별 `simple_return`, `log_return`, `tradable` 등),
`features.parquet`(RSI·MACD·변동성), `benchmark.parquet`(KOSPI `simple_return`),
`dividends.parquet`이다. C의 성과 평가는 `simple_return`을 사용한다. 첫 거래일의
벤치마크 수익률은 전일 값이 없어 NaN일 수 있으며, 이를 임의로 0으로 채우지 않는다.
나머지 필수 열·자산·거래일이 불일치하면 입력 계층에서 오류를 낸다.
