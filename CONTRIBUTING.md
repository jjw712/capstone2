# 협업 규칙

팀이 같은 방식으로 작업하기 위한 규칙이다. 바꾸고 싶으면 이 파일을 고치는 PR을 올린다.

## 작업 흐름

1. **Issue 만들기**: 템플릿(기능·버그·실험)을 고르고 담당자를 지정한다. 오타 같은 작은 수정은 Issue 없이 PR만 올려도 된다.
2. **브랜치 만들기**: 최신 `main`에서 `<타입>/<이슈번호>-<짧은-영어-설명>`으로 만든다. 예: `feat/12-rsi-macd`. 한글 브랜치 이름은 터미널에서 다루기 불편해서 영어로 쓴다.
3. **작업·커밋**: 브랜치 안의 커밋 메시지는 자유롭게 쓰되, 리뷰어가 알아볼 수 있게 쓴다.
4. **PR 올리기**: 제목은 아래 형식을 따르고, 설명에 `Closes #이슈번호`를 쓴다.
5. **머지**: CI가 통과하면 작성자가 **Squash and merge** 한다. 머지한 브랜치는 자동으로 지워진다. 공통 파일이나 다른 담당의 폴더를 바꾼 PR은 리뷰 승인을 먼저 받는다 (아래 "리뷰" 참고).

`main`에는 직접 푸시하지 않는다 (저장소 설정으로 막혀 있다). PR을 거쳐야 main에 들어가기 전에 CI가 돌고, 과제 명세가 요구하는 Issue·PR 개발 이력도 남는다. `main`은 항상 `pytest`와 `docker compose up`이 되는 상태로 유지한다.

## PR 제목 = main에 남는 커밋 메시지

스쿼시 머지를 쓰므로 PR 제목이 그대로 `main`의 커밋 메시지가 된다. 형식이 틀리면 CI의 `pr-title` 검사가 실패해서 머지할 수 없고, PR 제목을 고치면 다시 검사한다.

```
<타입>(<범위>): <무엇을 했는지>
```

| 타입 | 언제 | 예시 |
|---|---|---|
| `feat` | 새 기능 | `feat(research): Self-Correction 재검색 노드 추가` |
| `fix` | 버그 수정 | `fix(baselines): MVO 비중 합이 1을 넘는 문제 수정` |
| `refactor` | 동작은 그대로인 구조 변경 (이름 변경 포함) | `refactor(trading_env): env/ 폴더 이름을 trading_env/로 변경` |
| `test` | 테스트 추가·수정 | `test(evaluation): 미래 정보 누수 점검 테스트 추가` |
| `docs` | README, `docs/`, 리포트 | `docs: README에 실행 방법 추가` |
| `exp` | 실험 설정 변경·결과 기록 | `exp(rl): λ 0.5~5.0 탐색 설정 추가` |
| `chore` | 의존성, Docker, CI, 기타 | `chore(infra): CI에 pip 캐시 추가` |

- **타입·범위**는 영어 소문자로 쓴다. `exp`를 따로 두는 이유는 리포트를 쓸 때 `git log --grep "^exp"` 한 줄로 실험 이력만 뽑기 위해서다.
- **범위**는 바꾼 폴더 이름이다: `data`, `baselines`, `trading_env`, `risk`, `rl`, `research`, `evaluation`, `storage`, `services`, `contracts`, `api`, `dashboard`, `configs`, `infra`(Docker·CI·의존성). 폴더가 곧 담당 역할이라 범위만 봐도 누구 작업인지 보인다. 여러 폴더를 건드렸으면 주된 하나만 쓰고, 애매하면 생략한다 (위 `docs` 예시).
- **설명**은 한국어 50자 이내로, 마침표 없이 쓴다. "수정", "업데이트", "WIP"처럼 무엇을 했는지 안 보이는 말은 쓰지 않는다. 바뀐 파일 목록은 git이 기록하므로 적지 않는다.
- 다른 사람 코드를 깨는 변경은 타입 뒤에 `!`를 붙이고, 누가 무엇을 고쳐야 하는지 PR 설명에 적는다. 예: `feat(contracts)!: RiskTag에 verified 필드 추가`

## 리뷰

- 자기 담당 폴더만 바꾼 PR은 리뷰 없이 머지해도 된다. 의견이 필요하면 원하는 사람에게 리뷰를 요청한다.
- 다른 담당의 폴더를 바꿨다면 그 담당에게 리뷰를 받는다. 예: A가 짜는 `evaluation/metrics.py`는 C의 폴더에 있으므로, A가 고치면 C가, C가 고치면 A가 리뷰한다.
- 아래 **공통 파일**을 바꾼 PR은 영향을 받는 담당의 승인을 받은 뒤 머지한다. git 충돌 없이 합쳐져도 다른 사람 코드가 조용히 틀린 결과를 낼 수 있기 때문이다.

| 공통 파일 | 리뷰할 사람 |
|---|---|
| `src/roboadvisor/contracts.py`, `docs/interfaces.md` | 전원 |
| `api/schemas.py` (API 요청·응답 형식) | 전원 |
| `configs/experiments.yaml` | A·B·C |
| `requirements.txt`, `requirements-dev.txt`, `dashboard/requirements.txt` | E |

- `.github/CODEOWNERS`에 GitHub 아이디를 채우면 공통 파일과 `evaluation/metrics.py`를 건드린 PR에 리뷰어가 자동으로 지정되고, 그 리뷰 승인 없이는 머지되지 않는다.
- 리뷰 요청을 받으면 이틀 안에 리뷰하고, 못 하면 PR에 댓글로 알린다.
- PR 하나에는 한 가지 일만 담는다. 범위를 하나로 쓸 수 없으면 PR을 나눈다.

## 코드·설정

- PR을 올리기 전에 `black .`, `flake8`, `pytest`를 통과시킨다. CI도 같은 검사를 한다.
- Dockerfile·의존성·`docker-compose.yml`을 바꾼 PR은 CI가 Docker 이미지를 빌드해 API와 대시보드가 실제로 뜨는지도 확인한다.
- 설정값은 코드에 직접 쓰지 않고 `configs/`에, 비밀 값은 `.env`에 둔다. `# 명세` 표시가 붙은 값은 바꾸지 않는다.
- 로직은 `src/roboadvisor/`에 두고, `scripts/`와 노트북은 불러 쓰기만 한다. 대시보드는 `src/`를 import 하지 않고 API로만 통신한다.
- 새 기능에는 테스트를 붙인다 (각자 자기 모듈 2개 이상).
- 라이브러리를 추가하면 `requirements.txt`에 버전을 고정하고 PR에 이유를 적는다.

## 공통 파일을 바꿀 때

- 바꾸기 전에 Issue로 알리고 관련 담당과 합의한다.
- `contracts.py`를 바꾸면 `docs/interfaces.md`와 `tests/fixtures/`도 같이 고친다.

## 실험 기록

- 실험은 `[실험]` Issue로 시작하고, 실험 ID는 `configs/experiments.yaml`의 `run_id_format`을 따른다.
- 결과는 `docs/experiments/_template.md`를 복사해 `docs/experiments/<실험 ID>.md`에 기록하고 `exp(...)` PR로 올린다.
- 모델 등 산출물은 `artifacts/runs/<실험 ID>/`에 두고, Git 대신 팀 공유 드라이브로 주고받는다. 제출용 그림·표만 `reports/`에 올린다.

## 올리면 안 되는 것

- `.env`와 API 키
- `data/` 안의 파일 (뉴스는 재배포 금지)
- `artifacts/runs/` 안의 파일
- 노트북 출력 (올리기 전에 지운다)
