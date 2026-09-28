# 시스템 아키텍처

TODO: 제안 발표 전에 확정하고 README·리포트 1장에 넣는다.

```mermaid
flowchart LR
  subgraph offline["미리 실행 (scripts/)"]
    D1["가격 수집·전처리<br/>data"] --> T["PPO 학습<br/>trading_env · rl"]
    T --> E["Walk-Forward 평가<br/>evaluation"]
    E --> S[("artifacts/serving")]
    N["뉴스 수집·색인<br/>research"] --> V[("ChromaDB")]
  end
  subgraph online["요청 처리 (api/)"]
    API["FastAPI"] --> SV["services"]
    SV --> P["rl/policy<br/>모델 비중 → 리스크 규칙"]
    SV --> R["리서치 에이전트<br/>research"]
    SV --> DB[("storage<br/>결정·점검 기록")]
    R -- "리스크 태그" --> P
  end
  P --> S
  R --> V
  UI["Streamlit 대시보드"] -- "HTTP" --> API
```

- 무거운 계산(학습·백테스트·SHAP·ANOVA·임베딩)은 미리 실행하고, API는 결과를 읽거나 가벼운 추론만 한다 (요청당 5초).
- 대시보드는 API로만 통신한다.
- 백테스트와 서비스는 같은 `rl/policy.py`를 써서 같은 방식으로 비중을 정한다.
