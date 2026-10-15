"""원천 데이터 수집 — A->B 명세 부록 A.1/A.3.

KRX_ID/KRX_PW가 설정되면 pykrx가 그 둘을 환경변수에서 알아서 읽어 자동 로그인한다
(`pykrx.website.comm.auth.build_krx_session` 참고 — 이 파일이 로그인을 따로 처리할
필요는 없다). 그래서 여기 함수들은 전부 "로그인 됐으면 쓰는 진짜 엔드포인트 ->
안 되면 로그인 없이도 되는 근사치"로 떨어지는 구조다. KRX_ID/KRX_PW가 들어오면
코드를 안 고쳐도 자동으로 더 정확한 값을 쓰게 된다. 각 함수는 `(값, source_tag)`를
돌려줘서 이번 빌드가 실제로 어느 경로를 탔는지 조용히 묻히지 않게 한다.

2026-10-07 기준(KRX_ID/KRX_PW 아직 없음) 실측:
    - naver 수정 종가: FinanceDataReader. 로그인 불필요, 명세서가 지정한 소스.
    - 거래량/비조정종가: pykrx get_market_ohlcv(adjusted=False)와
      get_etf_ohlcv_by_date는 로그인 없이는 내부 ISIN 조회에서 실패한다(빈 결과).
      get_market_ohlcv(adjusted=True, 기본값)는 로그인 없이도 된다 — 지금은 이걸
      근사치로 쓴다.
    - KOSPI 지수: pykrx get_index_ohlcv는 로그인 필요. FinanceDataReader의 KS11은
      소스 자체가 ~3주 밀려 있어 거래일 달력으로 못 쓴다. yfinance `^KS11`로 대체.
    - 배당: yfinance Ticker(t+".KS").dividends. split-adjusted로 나온다(실측 확인:
      삼성전자 2017년 분기배당 140원 = 분할 전 7,000원 ÷ 50).
"""

from __future__ import annotations

import time

import pandas as pd
import requests

KRX_INTERVAL_SEC = 1.0  # 명세 A.3: 요청을 몰아 보내면 차단될 수 있어 1초 간격
RETRY_ATTEMPTS = 3  # data/dart.py::_get과 같은 패턴 — 일시적 네트워크 오류만 재시도
RETRY_BASE_DELAY_SEC = 5.0
_TRANSIENT_ERRORS = (
    requests.exceptions.RequestException,
    ConnectionError,
    TimeoutError,
    OSError,
)


def _with_retry(fn, *args, **kwargs):
    """naver/pykrx/yfinance 호출 중 네트워크가 잠깐 끊기는 경우를 재시도한다.
    무인 cron 실행(18:30) 한 번의 일시적 장애로 당일 갱신 전체가 실패하는 걸
    막는다 — dart.py의 _get은 이미 이렇게 하고 있었는데 이쪽엔 빠져 있었다."""
    last_exc: Exception | None = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            return fn(*args, **kwargs)
        except _TRANSIENT_ERRORS as exc:
            last_exc = exc
            if attempt == RETRY_ATTEMPTS - 1:
                raise
            time.sleep(RETRY_BASE_DELAY_SEC * (attempt + 1))
    raise last_exc  # pragma: no cover — 위 루프가 항상 return/raise로 끝남


def fetch_naver_adjusted_close(ticker: str, start: str, end: str) -> pd.Series:
    """FinanceDataReader 종가 (naver 수정 종가). simple_return의 P."""
    import FinanceDataReader as fdr

    df = _with_retry(fdr.DataReader, ticker, start, end)
    if df is None or df.empty:
        raise RuntimeError(f"FinanceDataReader returned no rows for {ticker}")
    return df["Close"].astype(float).rename(ticker)


def fetch_krx_volume_and_close(
    ticker: str, start: str, end: str, is_etf: bool
) -> tuple[pd.Series, pd.Series, str]:
    """(거래량, 비조정 종가, source_tag). KRX 로그인 되면 진짜 비조정값, 안 되면 근사치.

    source_tag: "krx_unadjusted"(로그인 성공, 진짜 비조정 종가) 또는
    "krx_adjusted_approx"(로그인 없음/실패, adjusted=True 근사치 — close_krx로
    8장 "최근 구간 KRX 대조"에 쓰면 안 됨, 거래량만 신뢰).
    """
    from pykrx import stock

    s, e = start.replace("-", ""), end.replace("-", "")
    if is_etf:
        try:
            df = _with_retry(stock.get_etf_ohlcv_by_date, s, e, ticker)
            if df is not None and not df.empty and "거래량" in df.columns:
                time.sleep(KRX_INTERVAL_SEC)
                close_col = "종가" if "종가" in df.columns else "NAV"
                return (
                    df["거래량"].astype(float).rename(ticker),
                    df[close_col].astype(float).rename(ticker),
                    "krx_unadjusted",
                )
        except Exception:  # noqa: BLE001
            pass
    else:
        try:
            df = _with_retry(stock.get_market_ohlcv, s, e, ticker, adjusted=False)
            if df is not None and not df.empty:
                time.sleep(KRX_INTERVAL_SEC)
                return (
                    df["거래량"].astype(float).rename(ticker),
                    df["종가"].astype(float).rename(ticker),
                    "krx_unadjusted",
                )
        except Exception:  # noqa: BLE001
            pass

    # 로그인 없이도 되는 경로로 떨어진다 — 거래량은 쓰되 종가는 근사치로 표시.
    df = _with_retry(stock.get_market_ohlcv, s, e, ticker)  # adjusted=True 기본값
    if df is None or df.empty:
        return (
            pd.Series(dtype=float, name=ticker),
            pd.Series(dtype=float, name=ticker),
            "unavailable",
        )
    time.sleep(KRX_INTERVAL_SEC)
    return (
        df["거래량"].astype(float).rename(ticker),
        df["종가"].astype(float).rename(ticker),
        "krx_adjusted_approx",
    )


def fetch_kospi_benchmark(start: str, end: str) -> tuple[pd.DataFrame, str]:
    """KOSPI 지수. (date, close, simple_return), source_tag.

    pykrx get_index_ohlcv(로그인 필요) -> yfinance ^KS11(로그인 불필요, 2026-10-07
    기준 당일자까지 나옴) 순. FinanceDataReader의 KS11은 실측 결과 소스가 밀려
    있어 시도하지 않는다(날짜가 거래일 달력 기준이라 밀리면 전체가 어긋난다).
    """
    from pykrx import stock

    try:
        df = _with_retry(
            stock.get_index_ohlcv, start.replace("-", ""), end.replace("-", ""), "1001"
        )
        time.sleep(KRX_INTERVAL_SEC)
        if df is not None and not df.empty:
            out = pd.DataFrame({"close": df["종가"].astype(float)})
            out.index.name = "date"
            out["simple_return"] = out["close"].pct_change()
            return out.reset_index(), "pykrx_1001"
    except Exception:  # noqa: BLE001
        pass

    import yfinance as yf

    raw = _with_retry(
        yf.download, "^KS11", start=start, end=end, auto_adjust=True, progress=False
    )
    if raw is None or raw.empty:
        raise RuntimeError("both pykrx 1001 and yfinance ^KS11 returned no rows")
    close = (
        raw["Close"]["^KS11"]
        if isinstance(raw.columns, pd.MultiIndex)
        else raw["Close"]
    )
    out = pd.DataFrame({"close": close.astype(float)})
    out.index.name = "date"
    out["simple_return"] = out["close"].pct_change()
    return out.reset_index(), "yfinance_ks11"


def fetch_dividends(ticker: str) -> pd.DataFrame:
    """yfinance 배당 기록. ex_date, amount (split-adjusted, 원)."""
    import yfinance as yf

    s = _with_retry(lambda: yf.Ticker(ticker + ".KS").dividends)
    if s is None or len(s) == 0:
        return pd.DataFrame(columns=["ex_date", "amount", "source"])
    df = s.rename("amount").reset_index()
    df = df.rename(columns={"Date": "ex_date"})
    df["ex_date"] = pd.to_datetime(df["ex_date"]).dt.tz_localize(None).dt.normalize()
    df["source"] = "yahoo"
    return df[["ex_date", "amount", "source"]]
