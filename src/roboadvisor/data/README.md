# data/ (A 데이터·퀀트)

가격 데이터를 받아 학습·평가에 쓸 형태로 만든다. 설정은 `configs/assets.yaml`, `configs/data.yaml`.
산출물(`returns`/`features`/`benchmark`/`dividends` parquet 4종)은 저장소 루트의
`data/processed/`에 쓴다 (Git 제외 — `python -m roboadvisor.data.build_processed`로 다시 만든다).

- `sources.py`: naver(FinanceDataReader) 수정 종가, pykrx 거래량·비조정 종가, KOSPI 벤치마크, 배당(yfinance) 수집
- `build_processed.py`: 전체 재생성 (`python -m roboadvisor.data.build_processed`) — 수익률·`adj_close` 리베이스·RSI/MACD/변동성 계산
- `update.py`: 매 거래일 장 마감 뒤 증분 갱신 (`python -m roboadvisor.data.update`). `KRX_ID`/`KRX_PW` 필요
- `preprocessing.py`: 워크포워드 구간별 정규화 통계 (`fit_normalization_stats`) — 학습 구간에서만 계산
- `validate.py`: 자동 검증 (`python -m roboadvisor.data.validate`) — 결측·미래 정보 누수·정규화 안정성 등
- `dart.py`: OpenDART 배당 공시로 `dividends.parquet` 건별 대조 (`python -m roboadvisor.data.dart`). `DART_API_KEY` 필요

주의: 정규화 통계는 학습 구간에서만 계산한다. 어떤 피처도 기준일 이후 데이터를 쓰면 안 된다
(`validate.py`의 lookahead·정규화 안정성 체크로 자동 확인).

> `collectors/`·`features.py`·`dataset.py`로 나누는 리팩터는 이번 PR 이후 별도로 진행한다
> (이슈 참고). 지금은 동작하는 버전을 그대로 옮겨왔다.
