# research/ (D 리서치·RAG)

뉴스·공시 기반 에이전틱 리서치. 설정은 `configs/research.yaml`.

- `collectors/`: 네이버 금융 RSS·DART 수집 (robots.txt 준수, 초당 1회 이하, 요약 300자 이내)
- `preprocessing.py`: 문서 정리, 중복·다른 회사 기사 제거
- `vector_store.py`: ChromaDB 저장 (메타데이터에 원문 URL 필수)
- `retrieval.py`, `graph.py`, `nodes/`: LangGraph 계획 → 검색 → 관련성 평가 → (부족하면 쿼리 수정·재검색) → 검증
- `risk_tags.py`: 위험 이벤트 → `contracts.RiskTag`
- `evaluation.py`: (제안) 고정 평가셋으로 검색 품질·출처 정확도 측정

모든 결과에는 출처가 있어야 하고, 단계별 생각은 `contracts.TraceStep`으로 남겨 대시보드에 보여 준다.
