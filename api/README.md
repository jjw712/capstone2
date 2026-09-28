# api/ (E 백엔드·화면)

FastAPI 서버. 요청을 받아 `roboadvisor.services`를 부르고 결과를 돌려준다. 계산 로직은 여기 두지 않는다.

- `main.py`: 앱 생성, 라우터 등록 (Swagger: `/docs`)
- `dependencies.py`: 모델·DB 같은 실행 자원 준비 (서버 시작 때 한 번)
- `schemas.py`: HTTP 요청·응답 형식 (`contracts.py`와 겹치면 재사용)
- `routers/`: 엔드포인트 하나에 파일 하나

| 엔드포인트 | 상태 |
|---|---|
| `GET /health` | 구현됨: 서버 상태·모델 로드 여부 |
| `POST /optimize` | 예정 |
| `POST /explain` | 예정 |
| `POST /research` | 예정 (결과를 바로 응답, 5초 이내) |
| `GET /backtest` | 예정 |

로컬 실행 (저장소 루트에서): `uvicorn api.main:app --reload`
