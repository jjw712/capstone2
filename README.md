# 에이전틱 RAG + 강화학습 통합 로보어드바이저

캡스톤디자인 2 · 38번 과제. PPO 강화학습 자산배분 엔진과 LangGraph 리서치 에이전트를 결합하고, 모든 비중 결정의 근거(SHAP·출처·리스크 태그)를 추적할 수 있게 만든다.

> 지금은 뼈대 단계다. `GET /health` API와 빈 대시보드 탭만 동작한다.

## 실행 (Docker)

```bash
cp .env.example .env
docker compose up --build
```

- API 문서(Swagger): http://localhost:8000/docs
- 대시보드: http://localhost:8501

첫 빌드는 torch 등을 설치하느라 오래 걸린다.

## 로컬 개발 환경

Python **3.12**가 필요하다 (numpy·scipy·shap 최신 버전이 3.12 이상만 지원). macOS는 14 이상.

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows PowerShell
# source .venv/bin/activate       # macOS·Linux
pip install -r requirements.txt -r requirements-dev.txt
pip install -e .
```

PR 올리기 전 확인:

```bash
pytest
black .
flake8
```

## 폴더 구조

폴더마다 README에 하는 일이 적혀 있다.

| 폴더 | 하는 일 | 담당 |
|---|---|---|
| `configs/` | 모든 설정값 (YAML) | 파일별 |
| `src/roboadvisor/` | 핵심 코드: 데이터·강화학습·평가·리서치·DB·연결 | 하위 폴더별 |
| `api/` | FastAPI 서버 | E |
| `dashboard/` | Streamlit 화면 (API로만 통신) | E, 탭 내용은 각 담당 |
| `scripts/` | 명령줄 실행 진입점 | 스크립트별 |
| `tests/` | pytest 테스트·예시 자료 | 전원 |
| `data/` | 실제 데이터 (Git 제외) | A·D |
| `artifacts/` | 실험 산출물·서비스용 모델 | B·C |
| `reports/` | 제출용 그림·표·리포트 PDF | C·A |
| `notebooks/` | 탐색용 노트북 | 전원 |
| `docs/` | 인터페이스·아키텍처·실험 기록 | A·C |

역할: A 데이터·퀀트 · B 강화학습 · C 설명·평가 · D 리서치·RAG · E 백엔드·화면

## 협업 규칙

- 작업은 Issue로 시작하고 `main`에는 PR로만 합친다. CI(black·flake8·pytest)가 통과해야 한다.
- PR 리뷰는 결과물을 받아 쓰는 사람이 한다: A의 PR은 B, B는 C, C는 A, D는 E, E는 D. `.github/CODEOWNERS`에 아이디를 채우면 자동으로 지정된다.
- `src/roboadvisor/contracts.py`, `configs/experiments.yaml`, API 형식을 바꾸면 전원에게 알린다.
- 설정값은 코드에 직접 쓰지 않고 `configs/`나 `.env`로 뺀다.
- `.env`, `data/` 안의 파일, `artifacts/runs/`는 커밋하지 않는다.

## 제출 전 채울 항목

과제 명세의 README 필수 항목.

- [ ] 시스템 아키텍처 다이어그램 (`docs/architecture.md`)
- [ ] 보상 함수 설계 근거
- [ ] 성능 지표 요약표 (12개 지표, 벤치마크·동일가중·MVO 대비, API 응답시간)
- [ ] ANOVA 검증 결과 요약
- [ ] 에러 분석 및 개선 방향

## 면책 조항

본 시스템은 교육 목적으로 개발되었으며 실제 투자 조언에 사용할 수 없습니다. 백테스트 성과는 미래 수익을 보장하지 않습니다.
