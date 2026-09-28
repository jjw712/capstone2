# artifacts/

모델과 실험 산출물.

**`runs/<실험 ID>/`**: 실험 한 번의 결과 묶음. Git에 올리지 않고 팀 공유 드라이브로 주고받는다 (TODO: 위치 확정). 실험 ID 형식은 `configs/experiments.yaml`의 `run_id_format`.

```
config.yaml                실제로 쓴 설정
manifest.json              기간·자산/피처 순서·버전·시드 (contracts.RunManifest)
model.zip
preprocessing/             학습 때 쓴 정규화 정보
metrics.json
portfolio_history.parquet
learning_curve.csv
```

**`serving/`**: API가 읽는 묶음. **Git에 올린다.** 평가자가 clone 후 `docker compose up`만 해도 모델이 로드되고 성과가 조회되도록, 고른 모델 묶음과 `/backtest`·ANOVA·SHAP 조회용 결과 파일을 여기 둔다.
