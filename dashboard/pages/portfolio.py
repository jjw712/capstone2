"""포트폴리오 현황 탭 (내용 담당: A)."""

from components.common import page_placeholder

page_placeholder(
    "포트폴리오 현황",
    owner="A 데이터·퀀트",
    todo=[
        "현재 자산 비중 (POST /optimize)",
        "누적 수익률 차트 (GET /backtest)",
    ],
)
