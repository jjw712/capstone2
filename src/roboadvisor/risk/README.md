# risk/ (B 강화학습, D와 연동)

리스크 태그와 Safe-Guard 규칙. 설정은 `configs/trading.yaml`.

- `safeguards.py`: MDD 감시, 리스크 태그 → 비중 상한 규칙 (필수 경로)
- `features.py`: 리스크 태그 → 관측 피처 변환 (관측 경로 실험용)

입력 태그 형식은 `contracts.RiskTag`. 규칙이 비중을 바꾸지 않았더라도 규칙 실행 여부와 적용 전후 비중을 남긴다.
