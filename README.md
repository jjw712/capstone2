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
# source .venv/Scripts/activate   # Windows Git Bash
# source .venv/bin/activate       # macOS·Linux
pip install -r requirements.txt -r requirements-dev.txt
pip install -e .
```

PowerShell에서 스크립트 실행이 막혀 `Activate.ps1`이 안 되면 Git Bash에서 두 번째 줄 명령을 쓴다.

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
| `docs/` | 인터페이스·아키텍처·실험 기록·회의록 | A·C |

역할: A 데이터·퀀트 · B 강화학습 · C 설명·평가 · D 리서치·RAG · E 백엔드·화면

## 협업 규칙

Issue → 브랜치 → PR → CI 통과 → Squash and merge 순서로 작업한다. PR 제목(`<타입>(<범위>): <무엇을 했는지>`)이 그대로 main의 커밋 메시지가 되고, 공통 파일이나 다른 담당의 폴더를 바꾼 PR만 리뷰를 받는다. 자세한 규칙은 [CONTRIBUTING.md](CONTRIBUTING.md)에 있다.

## 제출 전 채울 항목

과제 명세의 README 필수 항목.

- [ ] 시스템 아키텍처 다이어그램 (`docs/architecture.md`)
- [ ] 보상 함수 설계 근거
- [ ] 성능 지표 요약표 (12개 지표, 벤치마크·동일가중·MVO 대비, API 응답시간)
- [ ] ANOVA 검증 결과 요약
- [ ] 에러 분석 및 개선 방향

## 면책 조항

본 시스템은 교육 목적으로 개발되었으며 실제 투자 조언에 사용할 수 없습니다. 백테스트 성과는 미래 수익을 보장하지 않습니다.
