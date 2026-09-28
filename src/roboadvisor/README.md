# src/roboadvisor/

핵심 코드 패키지. `scripts/`, `api/`, `tests/`, 노트북이 모두 여기서 import 한다 (`pip install -e .` 후 `from roboadvisor.data import ...`).

| 폴더/파일 | 하는 일 | 담당 |
|---|---|---|
| `config.py` | 설정(YAML)·환경 변수 로더 | E |
| `contracts.py` | 역할 사이 데이터 형식 (Pydantic) | A, 변경은 전원 합의 |
| `data/` | 가격 수집·전처리·기술지표·기간별 데이터 | A |
| `baselines/` | MVO·동일가중 기준 전략 | A |
| `env/` | Gymnasium 거래 환경·거래비용 계산·보상 함수 | B |
| `risk/` | Safe-Guard·리스크 태그 규칙 | B (D와 연동) |
| `rl/` | PPO 학습·추론·모델 묶음 로드 | B |
| `evaluation/` | Walk-Forward·백테스트·지표·통계·SHAP | C |
| `research/` | 뉴스 수집·ChromaDB·LangGraph 에이전트·리스크 태그 생성 | D |
| `storage/` | 관계형 DB (결정·점검 기록) | E |
| `services/` | 기능 연결 (API가 호출하는 흐름) | E |

## 비중 결정 흐름

1. `data`: 기준일(`as_of`)까지의 피처
2. `research` → `risk`: 기준일 이전에 공개된 리스크 태그
3. `rl/policy.py`: 모델 비중 → 리스크 규칙 → 최종 비중. **백테스트와 서비스가 이 함수를 같이 쓴다**
4. `services/portfolio.py`: 1~3을 부르고 `storage`에 결정 기록
5. `api` → `dashboard`

다른 역할 폴더의 내부 함수를 직접 고치지 말고, `contracts.py` 형식과 공개 함수로 주고받는다.
