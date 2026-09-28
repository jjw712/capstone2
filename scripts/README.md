# scripts/

명령줄에서 실행하는 진입점. 인자를 받아 `src/roboadvisor`의 함수를 부르기만 하고, 로직은 여기 두지 않는다.

| 스크립트 | 하는 일 | 담당 |
|---|---|---|
| `collect_prices.py` | 가격 데이터 수집 → `data/raw/` | A |
| `build_features.py` | 전처리·피처 → `data/processed/` | A |
| `ingest_news.py` | 뉴스 수집·ChromaDB 색인 (처음 실행할 때 필요) | D |
| `train.py` | PPO 한 번 학습 → `artifacts/runs/` | B |
| `run_experiment.py` | Walk-Forward 전체 실행 (학습·평가) | C |
| `run_shap.py` | SHAP 계산·그림 | C |
| `run_anova.py` | ANOVA 3종 | C |
| `evaluate_research.py` | 리서치 품질 평가 | D·C |
| `measure_latency.py` | 엔드포인트별 응답시간 측정 | E |

아직 파일은 없다. 기능을 구현할 때 이 이름으로 추가한다.
