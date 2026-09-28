# tests/

pytest 테스트. 각자 자기 모듈 테스트를 2개 이상 쓴다 (명세: 전체 10개 이상). 저장소 루트에서 `pytest`로 실행한다.

- `unit/`: 함수 하나의 계산·처리 확인 (예: 수수료 차감, MDD 계산, 미래 정보 누수 없음)
- `integration/`: 여러 모듈을 잇는 흐름과 API 확인
- `fixtures/`: 테스트·개발용 작은 가짜 자료. 모두 `sample_`로 시작하고 실제 데이터가 아니다
  - `sample_*.json`: `contracts.py` 형식 예시. 실제 데이터가 나오기 전에 각자 이걸로 개발한다
  - `sample_prices.csv`: 합성 가격 (자산 4개 × 60 거래일, ffill·결측 제거 테스트용 빈칸 2개)

지금 있는 테스트는 설정의 명세 고정값(`unit/test_config.py`), 형식 예시(`unit/test_contracts.py`), `/health`(`integration/test_api_health.py`)를 확인한다.
