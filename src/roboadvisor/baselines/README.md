# baselines/ (A 데이터·퀀트)

강화학습과 비교할 기준 전략. 설정은 `configs/baselines.yaml`.

- `equal_weight.py`: 동일가중, 월 1회 리밸런싱
- `mvo.py`: 평균-분산 최적화 (252일 공분산, 공매도 금지, 자산당 40% 이하, `scipy.optimize.minimize`, 수렴 확인)

거래비용은 `env/accounting.py`를 같이 써서 강화학습과 같은 조건으로 비교한다.
