# evaluation/ (C 설명·평가)

실험을 돌리고 결과를 비교·해석한다. 설정은 `configs/evaluation.yaml`, `configs/experiments.yaml`.

- `walk_forward.py`: 기간마다 B의 학습 함수 → 평가 순서로 실행. 같은 실험 ID 결과가 이미 있으면 학습을 건너뛴다
- `backtest.py`: DRL·MVO·동일가중·벤치마크를 같은 조건으로 평가 (`env/accounting.py`, `rl/policy.py` 사용)
- `metrics.py`: 12개 지표 (A가 구현, C가 사용)
- `statistics.py`: ANOVA 3종·Tukey HSD·η²
- `explain.py`: SHAP Summary·Force Plot

실험 결과는 `artifacts/runs/`에, 제출용으로 고른 그림·표는 `reports/`에 둔다.
