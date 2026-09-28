# services/ (E 백엔드, 기능 담당자 공동 검토)

여러 모듈을 이어 붙이는 흐름. API 라우터는 여기 함수만 부른다.

- `portfolio.py`: 기준일 데이터·리스크 태그 조회 → `rl/policy.py` → 결정 기록
- `research.py`: 질문 → 리서치 에이전트 → 결과 저장
- `explain.py`: 결정 조회 → 저장된 SHAP 조회 (없으면 계산)
- `reporting.py`: `artifacts/serving/`의 성과·실험 결과 조회

계산 로직은 여기 두지 않는다. 비중 계산은 `rl/`, 규칙은 `risk/`, 평가는 `evaluation/`에 둔다.
