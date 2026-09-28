# data/

실제 데이터를 두는 곳. 폴더 구조와 이 README만 Git에 올라가고, 안의 파일은 올라가지 않는다 (뉴스는 재배포 금지, 가격은 스크립트로 다시 받을 수 있다).

- `raw/`: 수집한 원본 (가격·벤치마크·뉴스)
- `processed/`: 전처리 결과 (`returns.parquet`, `features.parquet` 등)
- `chroma/`: ChromaDB 벡터 DB. 처음 실행할 때 `scripts/ingest_news.py`로 만든다
- `app/`: SQLite DB 파일 (SQLite를 쓸 경우)
