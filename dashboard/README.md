# dashboard/ (E 틀, 탭 내용은 데이터를 만든 사람)

Streamlit 대시보드. 모델이나 `src/`를 import 하지 않고 API와 HTTP로만 통신한다 (명세의 MSA 요건). 그래서 전용 `requirements.txt`와 Dockerfile을 따로 둔다.

- `app.py`: 탭 목록
- `client.py`: API 호출은 전부 여기서
- `components/`: 공통 표시 (API 상태, 면책 문구)
- `pages/`: 탭별 화면

| 탭 | 파일 | 내용 담당 |
|---|---|---|
| 포트폴리오 현황 | `pages/portfolio.py` | A |
| 강화학습 성과 | `pages/rl_performance.py` | B |
| SHAP 해석 | `pages/shap_explain.py` | C |
| 에이전트 리서치 | `pages/research.py` | D |
| ANOVA 검증 결과 | `pages/anova.py` | C |
| 리스크 모니터링 | `pages/risk_monitor.py` | E |

로컬 실행: `pip install -r dashboard/requirements.txt` 후 `streamlit run dashboard/app.py`. API 주소는 환경 변수 `API_URL` (기본 `http://localhost:8000`).
