# storage/ (E 백엔드, D 협업)

관계형 DB. API 서버 없이 스크립트에서도 쓸 수 있게 `api/` 밖에 둔다. 주소는 `.env`의 `DATABASE_URL`.

- `database.py`: 연결·초기화 (SQLAlchemy)
- `tables.py`: 테이블 정의 (결정 기록, 점검 기록)
- `repositories/`: 저장·조회 함수

뉴스 원문 메타데이터는 ChromaDB 한 곳에만 둔다. DB 종류(SQLite/PostgreSQL)는 회의에서 확정한다.
