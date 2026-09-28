# configs/

모든 설정값을 모아 두는 곳. 코드에 숫자를 직접 쓰지 말고 `roboadvisor.config.load_config("파일명")`으로 읽는다. API 키 같은 비밀 값은 여기가 아니라 `.env`에 둔다. 파일 저장 경로는 여기 두지 않고 `roboadvisor.config.get_settings()`의 `raw_dir`, `processed_dir`, `chroma_dir`, `runs_dir`, `serving_dir`를 쓴다.

| 파일 | 내용 | 관리 |
|---|---|---|
| `assets.yaml` | 자산 목록·순서·벤치마크 | A |
| `data.yaml` | 수집 기간·전처리·기술지표 | A |
| `baselines.yaml` | MVO·동일가중 기준 전략 | A |
| `trading.yaml` | 거래비용·비중 제약·Safe-Guard·리스크 태그 규칙 | B |
| `rl.yaml` | 관측·행동 공간, 보상 함수, PPO | B |
| `evaluation.yaml` | 12개 지표·ANOVA·시장 국면·SHAP | C |
| `experiments.yaml` | Walk-Forward 기간·시드·비교 전략 (A·B·C 공통 기준) | C |
| `research.yaml` | 뉴스 수집·검색·재검색·LLM | D |

- `# 명세` 표시가 붙은 값은 과제 명세로 정해진 값이다. 바꾸면 `tests/unit/test_config.py`가 실패한다.
- `# TODO` 표시는 회의에서 확정할 값이다.
- `experiments.yaml`을 바꾸면 A·B·C에게 알린다.
