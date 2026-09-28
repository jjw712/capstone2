# trading_env/ (B 강화학습)

Gymnasium 규격의 포트폴리오 거래 환경. 설정은 `configs/trading.yaml`, `configs/rl.yaml`. (`.env` 비밀 키나 가상환경과는 관계없다.)

- `portfolio_env.py`: 관측(과거 N일 수익률·현재 비중·기술지표), 행동(비중), 에피소드 진행
- `accounting.py`: 주문·보유량·거래비용(수수료 0.015%, 슬리피지 0.05%)·자산가치 계산. **백테스트도 이 모듈을 쓴다**
- `rewards.py`: 보상 3종 (r_t / 샤프 / r_t − λ·MDD)

Safe-Guard(MDD 15% 초과 시 조기 종료)는 `risk/safeguards.py`를 불러 쓴다.
