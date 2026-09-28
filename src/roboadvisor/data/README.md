# data/ (A 데이터·퀀트)

가격 데이터를 받아 학습·평가에 쓸 형태로 만든다. 설정은 `configs/assets.yaml`, `configs/data.yaml`.

- `collectors/`: yfinance·pykrx 수정주가 수집
- `preprocessing.py`: 로그 수익률, Forward Fill 후 남은 결측 제거, 정규화
- `features.py`: RSI·MACD 등 기술적 지표
- `dataset.py`: 기준일·학습/평가 구간별 데이터 제공

주의: 정규화 통계는 학습 구간에서만 계산한다. 어떤 피처도 기준일 이후 데이터를 쓰면 안 된다.
