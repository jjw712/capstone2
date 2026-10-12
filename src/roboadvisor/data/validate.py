"""A->B 데이터 명세 8장 검증 기준을 자동으로 돌린다.

    python -m roboadvisor.data.validate

`python -m roboadvisor.data.build_processed`를 먼저 돌려서 data/processed/*.parquet가
있어야 한다. 통과/실패만 보고 수치를 다시 베끼지 않는다 — 전부 parquet에서
그대로 읽는다.
"""

from __future__ import annotations

import sys
from zoneinfo import ZoneInfo

import FinanceDataReader as fdr
import pandas as pd

from .build_processed import indicators, load_config
from .preprocessing import fit_normalization_stats, load_processed

# 명세 8장 표 그대로. "±0.02 정도 차이는 정상"이 명세 원문.
DIVIDEND_RATIO_EXPECTED = {
    "105560": ("KB금융", 1.46),
    "005380": ("현대차", 1.35),
    "005930": ("삼성전자", 1.24),
    "069500": ("KODEX 200", 1.19),
    "148070": ("국고채10년", 1.19),
}
DIVIDEND_RATIO_TOL = 0.02
SPLIT_DAYS = {"005930": "2018-05-04", "035420": "2018-10-12"}
SPLIT_TOL = 0.30
NAN_FREE_FROM = "2019-01-02"

_naver_cache: dict[tuple[str, str, str], pd.Series] = {}


def _naver_close(ticker: str, start: str, end: str) -> pd.Series:
    """validate 한 번 실행 안에서 같은 (ticker, start, end) 재조회를 피한다."""
    key = (ticker, start, end)
    if key not in _naver_cache:
        _naver_cache[key] = fdr.DataReader(ticker, start, end)["Close"]
    return _naver_cache[key]


def _last_settled_date(dates) -> pd.Timestamp:
    """오늘(KST) 날짜 행은 비교에서 뺀다. 장중에 재검증하면 naver 재조회 시점마다
    당일 시세가 계속 움직여서, 저장된 값과 방금 받은 값이 우연히 달라질 수 있다
    (2026-10-12 실측: 장중 수동 재검증 때 ETF 6종 전부 양방향으로 작은 오차로 FAIL
    했다가, 같은 날 다시 돌리면 오차 패턴이 또 바뀌었다 — 숫자 오류가 아니라
    타이밍 문제였다). 전날까지만 비교하면 cron이든 수동이든 언제 돌려도 안정적이다."""
    today = pd.Timestamp.now(tz=ZoneInfo("Asia/Seoul")).normalize().tz_localize(None)
    dates = pd.DatetimeIndex(dates)
    settled = dates[dates < today]
    return settled.max() if len(settled) else dates.max()


def check_row_count(returns: pd.DataFrame, n_assets: int) -> bool:
    n_dates = returns["date"].nunique()
    expected = n_dates * n_assets
    ok = len(returns) == expected and not returns.duplicated(["date", "ticker"]).any()
    print(
        f"[row_count] {len(returns)} rows, expect {n_dates}*{n_assets}={expected}, dup={returns.duplicated(['date','ticker']).sum()} -> {'OK' if ok else 'FAIL'}"
    )
    return ok


def check_split_days(returns: pd.DataFrame) -> bool:
    """2018년 분할일 체크. start_date가 2019-01-01로 당겨진 뒤로는 이 날짜 자체가
    배포 범위 밖이라 행이 없는 게 정상이다 — 그때는 실패가 아니라 스킵으로 보고한다
    (데이터 품질 문제가 아니라 '애초에 그 구간을 안 준다'는 것뿐이므로).
    """
    ok = True
    min_date = returns["date"].min()
    for ticker, day in SPLIT_DAYS.items():
        if pd.Timestamp(day) < min_date:
            print(
                f"[split] {ticker} {day}: 배포 범위({min_date.date()}~) 밖이라 스킵 -> OK"
            )
            continue
        row = returns[(returns.ticker == ticker) & (returns.date == pd.Timestamp(day))]
        if row.empty:
            print(f"[split] {ticker} {day}: no row -> FAIL")
            ok = False
            continue
        r = float(row["simple_return"].iloc[0])
        passed = abs(r) <= SPLIT_TOL
        ok &= passed
        print(
            f"[split] {ticker} {day}: simple_return={r:.4f} (tol ±{SPLIT_TOL}) -> {'OK' if passed else 'FAIL'}"
        )
    return ok


def dividend_ratio(
    returns: pd.DataFrame, ticker: str, start: str, end: str, is_etf: bool
) -> float:
    """명세 8장: (adj_close 상승 배율) ÷ (가격만의 상승 배율).
    가격만 = 주식은 naver 수정가, ETF는 KRX 종가(returns.parquet의 close_krx)."""
    sub = returns[
        (returns.ticker == ticker) & (returns.date >= start) & (returns.date <= end)
    ]
    sub = sub.set_index("date").sort_index()
    adj_gain = sub["adj_close"].iloc[-1] / sub["adj_close"].iloc[0]
    if is_etf:
        px = sub["close_krx"]
    else:
        px = _naver_close(ticker, start, end)
    price_gain = px.iloc[-1] / px.iloc[0]
    return adj_gain / price_gain


def check_dividend_ratios(returns: pd.DataFrame, end="2026-10-02") -> bool:
    """배당 반영 비율. 명세 기대값(KB 1.46 등)은 2018-01-02 시작 기준이라, 배포 구간이
    그날 시작할 때만 ±허용폭으로 비교하고, 아니면 실측값만 보고한다. 배당 금액 자체의
    정확성은 data/dart.py의 건별 대조가 검증한다.
    """
    ok = True
    assets, _, _ = load_config()
    asset_class = {a["ticker"]: a["asset_class"] for a in assets}
    start = returns["date"].min().strftime("%Y-%m-%d")
    use_spec_expected = start == "2018-01-02"
    for ticker, (name, expected) in DIVIDEND_RATIO_EXPECTED.items():
        if returns[returns.ticker == ticker].empty:
            print(f"[dividend_ratio] {ticker} ({name}): no rows -> FAIL")
            ok = False
            continue
        ratio = dividend_ratio(
            returns, ticker, start, end, is_etf=asset_class[ticker] != "kr_stock"
        )
        if use_spec_expected:
            passed = abs(ratio - expected) <= DIVIDEND_RATIO_TOL
            ok &= passed
            print(
                f"[dividend_ratio] {ticker} ({name}): ratio={ratio:.3f} expect~{expected} (tol ±{DIVIDEND_RATIO_TOL}) -> {'OK' if passed else 'FAIL'}"
            )
        else:
            print(
                f"[dividend_ratio] {ticker} ({name}): ratio={ratio:.3f} over {start}~{end} (배포 구간이 2018-01-02가 아니라 명세 기대값과 직접 비교 안 함; DART 대조가 금액 정확성을 담보) -> OK"
            )
    return ok


def check_etf_distributions_counted_once(
    returns: pd.DataFrame, dividends: pd.DataFrame
) -> bool:
    """ETF 분배금 이중계산 방지. naver ETF 가격은 분배금 반영 수정가라 adj_close 상승 배율이
    naver 가격 배율과 같아야 하고(D를 더하지 않음), KRX 비조정 종가 배율보다는 커야 한다
    (분배금이 실제로 들어 있음). dividends.parquet에는 주식만 있어야 한다(명세 5장)."""
    assets, _, _ = load_config()
    etfs = [a["ticker"] for a in assets if a["asset_class"] != "kr_stock"]
    stocks = {a["ticker"] for a in assets if a["asset_class"] == "kr_stock"}
    ok = set(dividends["ticker"]) <= stocks
    print(
        f"[etf_dist] dividends.parquet tickers ⊆ 주식 5개: {sorted(set(dividends['ticker']))} -> {'OK' if ok else 'FAIL'}"
    )
    start = returns["date"].min().strftime("%Y-%m-%d")
    end_ts = _last_settled_date(returns["date"].unique())
    end = end_ts.strftime("%Y-%m-%d")
    for t in etfs:
        sub = (
            returns[(returns.ticker == t) & (returns.date <= end_ts)]
            .set_index("date")
            .sort_index()
        )
        adj_gain = sub["adj_close"].iloc[-1] / sub["adj_close"].iloc[0]
        naver = _naver_close(t, start, end)
        naver_gain = naver.iloc[-1] / naver.iloc[0]
        krx_gain = sub["close_krx"].iloc[-1] / sub["close_krx"].iloc[0]
        vs_naver = adj_gain / naver_gain
        vs_krx = adj_gain / krx_gain
        passed = abs(vs_naver - 1) < 1e-6 and vs_krx >= 1 - 1e-6
        ok &= passed
        print(
            f"[etf_dist] {t}: adj/naver={vs_naver:.6f} (1이어야 함), adj/KRX={vs_krx:.3f} (분배금 효과) -> {'OK' if passed else 'FAIL'}"
        )
    return ok


def check_no_nan_from(features: pd.DataFrame, start=NAN_FREE_FROM) -> bool:
    sub = features[features.date >= pd.Timestamp(start)]
    n_nan = int(sub[["rsi", "macd", "volatility"]].isna().sum().sum())
    ok = n_nan == 0
    print(
        f"[nan] rsi/macd/volatility NaN count from {start}: {n_nan} -> {'OK' if ok else 'FAIL'}"
    )
    return ok


def check_benchmark_clean(benchmark: pd.DataFrame) -> bool:
    n_nan = int(benchmark.isna().sum().sum())
    ok = n_nan == 0
    print(f"[benchmark] NaN count: {n_nan} -> {'OK' if ok else 'FAIL'}")
    return ok


def check_no_lookahead(
    returns: pd.DataFrame, ticker: str = "005930", cut: str = "2023-06-30"
) -> bool:
    """명세 8장 "시점": cut 이후 데이터를 바꿔도 cut 이전 피처가 그대로인가."""
    _, _, cfg = load_config()
    sub = returns[returns.ticker == ticker].set_index("date").sort_index()
    cut_ts = pd.Timestamp(cut)
    base = indicators(sub["adj_close"], sub["log_return"], cfg)

    perturbed_sub = sub.copy()
    future = perturbed_sub.index > cut_ts
    perturbed_sub.loc[future, "adj_close"] *= 1.5
    perturbed_sub.loc[future, "log_return"] += 0.5
    perturbed = indicators(perturbed_sub["adj_close"], perturbed_sub["log_return"], cfg)

    diff = (
        (base[base.index <= cut_ts] - perturbed[perturbed.index <= cut_ts])
        .abs()
        .max()
        .max()
    )
    ok = diff < 1e-9
    print(
        f"[lookahead] {ticker}, cut={cut}: perturbing future rows changes past features by {diff} -> {'OK' if ok else 'FAIL'}"
    )
    return ok


def check_normalization_stable(
    returns: pd.DataFrame,
    features: pd.DataFrame,
    window_id="w1",
    fit_start="2019-01-02",
    fit_end="2022-06-30",
) -> bool:
    """명세 8장 "정규화": 계산 구간(fit_end) 뒤 데이터를 바꿔도 통계가 그대로인가."""
    stats_before = fit_normalization_stats(
        features, returns, window_id=window_id, fit_start=fit_start, fit_end=fit_end
    )

    r2, f2 = returns.copy(), features.copy()
    mask_r = r2["date"] > pd.Timestamp(fit_end)
    mask_f = f2["date"] > pd.Timestamp(fit_end)
    r2.loc[mask_r, "log_return"] = r2.loc[mask_r, "log_return"] * 10 + 5
    f2.loc[mask_f, ["rsi", "macd", "volatility"]] *= 10
    stats_after = fit_normalization_stats(
        f2, r2, window_id=window_id, fit_start=fit_start, fit_end=fit_end
    )

    merged = stats_before.merge(
        stats_after, on=["feature", "ticker"], suffixes=("_before", "_after")
    )
    diff = max(
        (merged["mean_before"] - merged["mean_after"]).abs().max(),
        (merged["std_before"] - merged["std_after"]).abs().max(),
    )
    ok = diff < 1e-9
    print(
        f"[normalization] {window_id} fit_end={fit_end}: perturbing post-fit_end data changes stats by {diff} -> {'OK' if ok else 'FAIL'}"
    )
    return ok


def check_recent_krx_crosscheck(
    returns: pd.DataFrame, start: str = "2026-09-01", tol: float = 0.01
) -> bool:
    """명세 8장 "최근 구간": naver 수정종가 vs close_krx(비조정) 1% 이내.

    close_krx_source가 krx_unadjusted가 아니면(KRX 로그인 없음) 비교 자체가
    의미 없으니 건너뛰고 OK로 둔다 — 이 체크는 "틀렸는지"가 아니라 "비교할
    수 있을 때 1% 넘는 날이 있는지 알아두기" 위한 것이다(명세서 자체가
    "1% 넘는 날이 있었음"을 정상 범위로 언급한다. 실패 기준이 아니라 보고용).
    """
    if "krx_unadjusted" not in set(returns["close_krx_source"].unique()):
        print(
            "[recent_krx] close_krx_source has no krx_unadjusted rows yet (no KRX login) -> SKIP (OK)"
        )
        return True

    end_ts = _last_settled_date(returns["date"].unique())
    recent = returns[
        (returns.date >= start)
        & (returns.date <= end_ts)
        & (returns.close_krx_source == "krx_unadjusted")
    ]
    if recent.empty:
        print(f"[recent_krx] {start}~{end_ts.date()}: no settled rows yet -> SKIP (OK)")
        return True
    end = recent["date"].max().strftime("%Y-%m-%d")
    n_over = 0
    for ticker in sorted(recent["ticker"].unique()):
        naver = _naver_close(ticker, start, end).rename("naver")
        sub = recent[recent.ticker == ticker].set_index("date")["close_krx"]
        merged = pd.concat([naver, sub], axis=1).dropna()
        if merged.empty:
            continue
        pct_diff = (merged["close_krx"] - merged["naver"]).abs() / merged["naver"]
        over = pct_diff[pct_diff > tol]
        if len(over):
            n_over += len(over)
            print(
                f"[recent_krx] {ticker}: {len(over)} day(s) >{tol:.0%} naver/KRX diff — {list(over.index.strftime('%Y-%m-%d'))}"
            )
    print(
        f"[recent_krx] {start}~{end}: {n_over} day(s) over {tol:.0%} total (spec says this is a known, non-fatal source discrepancy) -> OK"
    )
    return True


def main() -> int:
    returns, features, benchmark, dividends = load_processed("data/processed")
    returns["date"] = pd.to_datetime(returns["date"])
    features["date"] = pd.to_datetime(features["date"])

    n_assets = returns["ticker"].nunique()
    results = [
        check_row_count(returns, n_assets),
        check_split_days(returns),
        check_dividend_ratios(returns),
        check_etf_distributions_counted_once(returns, dividends),
        check_no_nan_from(features),
        check_benchmark_clean(benchmark),
        check_no_lookahead(returns),
        check_normalization_stable(returns, features),
        check_recent_krx_crosscheck(returns),
    ]
    all_ok = all(results)
    print()
    print("ALL CHECKS PASSED" if all_ok else "SOME CHECKS FAILED")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
