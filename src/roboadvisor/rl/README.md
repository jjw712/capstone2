# rl/ (B 강화학습)

PPO 학습과 추론. 설정은 `configs/rl.yaml`, 기간·시드는 `configs/experiments.yaml`.

- `train.py`: 기간·보상·시드 하나로 학습 → `artifacts/runs/<실험 ID>/`에 모델·설정·manifest·학습 곡선 저장
- `predict.py`: 저장된 모델로 비중 추론
- `policy.py`: 모델 비중 → 리스크 규칙 → 최종 비중. **백테스트와 서비스가 이 함수를 같이 쓴다** (DB·파일 접근 없음)
- `model_bundle.py`: 모델·정규화 정보·자산/피처 순서를 한 번에 로드하고 서로 맞는지 확인
