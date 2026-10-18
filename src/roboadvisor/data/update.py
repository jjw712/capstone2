"""매 거래일 장 마감 뒤 증분 갱신 (명세 1.2 "매일 갱신", 부록 A.3).

    set -a; source .env; set +a
    python -m roboadvisor.data.update

전체를 다시 받지 않고 마지막 저장일 이후만 붙인다. 명세 A.3 방식 그대로:
최근 며칠을 겹쳐 받아 P_{t-1}과 P_t를 같은 응답에서 꺼내 수익률을 구하고,
저장은 수익률과 누적한 adj_close를 기준으로 한다. 그래서 그 사이 액면분할로
수정가 전체가 다시 매겨져도 새 수익률은 틀리지 않는다. 겹친 날의 수익률이
저장값과 다르면 경고만 하고 과거 행은 고치지 않는다.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from . import sources
from .build_processed import OUT_DIR, build_returns_for_ticker, indicators, load_config

OVERLAP_DAYS = 5  # 겹쳐 받는 저장 거래일 수
FETCH_LOOKBACK_DAYS = 30  # 원천 호출 시작일 = 마지막 저장일 - 이만큼(달력일)
RETURN_TOL = 1e-9
SETTLE_BUFFER_DAYS = (
    2  # 가장 최근 이만큼의 거래일은 원천이 아직 확정 전일 수 있어 경고 대상에서 뺀다
)


def require_krx_login() -> None:
    """KRX 로그인 없이 돌면 close_krx·벤치마크가 조용히 근사치로 떨어져 기존 행과 출처가 섞인다."""
    missing = [k for k in ("KRX_ID", "KRX_PW") if not os.getenv(k)]
    if missing:
        raise SystemExit(
            f"[update] {', '.join(missing)} 환경변수가 없어 중단 (.env 확인)"
        )


def update(processed_dir: Path = OUT_DIR, end: str | None = None) -> dict:
    assets, _, cfg = load_config()
    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    returns = pd.read_parquet(processed_dir / "returns.parquet")
    features = pd.read_parquet(processed_dir / "features.parquet")
    benchmark = pd.read_parquet(processed_dir / "benchmark.parquet")
    dividends = pd.read_parquet(processed_dir / "dividends.parquet")

    last_date = returns["date"].max()
    fetch_start = (last_date - pd.DateOffset(days=FETCH_LOOKBACK_DAYS)).strftime(
        "%Y-%m-%d"
    )

    bench_raw, bench_tag = sources.fetch_kospi_benchmark(fetch_start, end)
    bench_raw["date"] = pd.to_datetime(bench_raw["date"])
    bench_raw = bench_raw.set_index("date").sort_index()
    new_dates = bench_raw.index[bench_raw.index > last_date]
    if len(new_dates) == 0:
        print(f"[update] 이미 최신 (마지막 저장일 {last_date.date()})")
        return {"new_days": 0, "warnings": []}

    saved_dates = pd.DatetimeIndex(sorted(benchmark["date"].unique()))
    overlap = saved_dates[-OVERLAP_DAYS:]
    calendar = overlap.append(new_dates)
    warnings: list[str] = []

    # naver 종가는 장 마감 직후에 받아도 하루이틀 안에 한 번 더 조용히 정정되는 경우가
    # 있다(2026-10 급락장에서 실측: 10/13 종가를 그날 장 마감 직후·10/15·10/16 세 번
    # 받아봤더니 10/15까지는 값이 계속 바뀌다가 10/16에야 안정됐다 — 하루 늦게 받아도
    # 안전하지 않았다). calendar의 가장 최근 SETTLE_BUFFER_DAYS 거래일은 아직
    # 확정 전일 수 있다고 보고 겹침 경고 대상에서 뺀다 — 그보다 오래된 날짜가
    # 바뀌는 것만 "원천 수정"으로 보고한다(그 경우는 진짜 이상 신호이므로).
    settled = (
        calendar[:-SETTLE_BUFFER_DAYS]
        if len(calendar) > SETTLE_BUFFER_DAYS
        else calendar[:0]
    )

    new_bench = bench_raw.loc[new_dates, ["close", "simple_return"]].reset_index()
    bench_check = bench_raw.loc[calendar, "simple_return"].iloc[1 : len(overlap)]
    bench_check_dates = bench_check.index.intersection(settled)
    if (
        len(bench_check_dates)
        and bench_check.loc[bench_check_dates]
        .sub(benchmark.set_index("date").loc[bench_check_dates, "simple_return"])
        .abs()
        .max()
        > RETURN_TOL
    ):
        warnings.append("benchmark: 겹친 날 수익률이 저장값과 다름")

    new_ret_rows, new_feat_rows, new_div_rows = [], [], []
    for a in assets:
        t = a["ticker"]
        r, d, ck = build_returns_for_ticker(
            t, a["asset_class"], fetch_start, end, calendar
        )
        r = r.merge(ck, on=["date", "ticker"])
        saved = returns[returns.ticker == t].set_index("date").sort_index()

        # 겹친 날(첫 행 제외 — 그 행은 앞날이 없어 0으로 둔 값) 수익률 대조.
        # 가장 최근 SETTLE_BUFFER_DAYS거래일은 settled에서 빠져 있어 대조 대상이 아니다.
        ov = r.set_index("date").loc[overlap[1:], "simple_return"]
        check_dates = ov.index.intersection(settled)
        diff = (
            (ov.loc[check_dates] - saved.loc[check_dates, "simple_return"]).abs().max()
            if len(check_dates)
            else 0.0
        )
        if diff > RETURN_TOL:
            warnings.append(
                f"{t}: 겹친 날 수익률이 저장값과 최대 {diff:.2e} 다름 (원천 수정 가능성)"
            )

        new = r[r["date"].isin(new_dates)].copy()
        new["adj_close"] = saved["adj_close"].iloc[-1] * np.cumprod(
            1.0 + new["simple_return"].to_numpy()
        )
        new_ret_rows.append(new[returns.columns])

        # 지표는 인과적이라 저장된 전체 이력 + 새 행으로 다시 계산해 새 행만 쓴다.
        hist = pd.concat(
            [
                saved[["adj_close", "log_return"]],
                new.set_index("date")[["adj_close", "log_return"]],
            ]
        )
        ind = indicators(hist["adj_close"], hist["log_return"], cfg)
        old_feat = (
            features[features.ticker == t]
            .set_index("date")
            .loc[overlap, ["rsi", "macd", "volatility"]]
        )
        feat_check_dates = overlap.intersection(settled)
        fdiff = (
            (ind.loc[feat_check_dates] - old_feat.loc[feat_check_dates])
            .abs()
            .max()
            .max()
            if len(feat_check_dates)
            else 0.0
        )
        if fdiff > 1e-9:
            warnings.append(f"{t}: 겹친 날 지표가 저장값과 최대 {fdiff:.2e} 다름")
        nf = ind.loc[new_dates].reset_index().rename(columns={"index": "date"})
        nf.insert(1, "ticker", t)
        new_feat_rows.append(nf[["date", "ticker", "rsi", "macd", "volatility"]])
        if not d.empty:
            new_div_rows.append(d)

    order = {a["ticker"]: i for i, a in enumerate(assets)}
    out_returns = pd.concat([returns, *new_ret_rows], ignore_index=True)
    out_features = pd.concat([features, *new_feat_rows], ignore_index=True)
    for df in (out_returns, out_features):
        df.sort_values(
            ["ticker", "date"],
            key=lambda s: s.map(order) if s.name == "ticker" else s,
            inplace=True,
            ignore_index=True,
        )
    out_bench = pd.concat([benchmark, new_bench[benchmark.columns]], ignore_index=True)
    out_div = pd.concat([dividends, *new_div_rows], ignore_index=True)
    out_div = out_div.drop_duplicates(["ticker", "ex_date"], keep="first").sort_values(
        ["ticker", "ex_date"],
        key=lambda s: s.map(order) if s.name == "ticker" else s,
        ignore_index=True,
    )

    out_returns.to_parquet(processed_dir / "returns.parquet", index=False)
    out_features.to_parquet(processed_dir / "features.parquet", index=False)
    out_bench.to_parquet(processed_dir / "benchmark.parquet", index=False)
    out_div.to_parquet(processed_dir / "dividends.parquet", index=False)

    print(
        f"[update] {len(new_dates)}일 추가: {new_dates.min().date()}~{new_dates.max().date()} "
        f"(KOSPI source={bench_tag}), 배당 {len(out_div) - len(dividends)}건 추가"
    )
    new_ret = pd.concat(new_ret_rows, ignore_index=True)
    days = ", ".join(d.strftime("%m/%d") for d in new_dates[:6]) + (
        " 등" if len(new_dates) > 6 else ""
    )
    print(f"[update] 수집 거래일: {days}")
    print(
        f"[update] 추가 행: returns {len(new_ret)}, features {sum(len(f) for f in new_feat_rows)}, "
        f"benchmark {len(new_bench)} (자산 {len(assets)}종 x {len(new_dates)}일)"
    )
    k = new_bench.iloc[-1]
    print(
        f"[update] 코스피 {k['date'].date()} 종가 {k['close']:,.2f} ({k['simple_return']:+.2%})"
    )
    added_div = out_div.merge(
        dividends[["ticker", "ex_date"]],
        on=["ticker", "ex_date"],
        how="left",
        indicator=True,
    )
    added_div = added_div[added_div["_merge"] == "left_only"]
    if len(added_div):
        items = ", ".join(
            f"{r.ticker} {r.ex_date.date()} {r.amount:g}원"
            for r in added_div.itertuples()
        )
        print(f"[update] 배당락 추가 {len(added_div)}건: {items}")
    n_krx = int((new_ret["close_krx_source"] == "krx_unadjusted").sum())
    print(f"[update] KRX 원본 종가: {n_krx}/{len(new_ret)}행")
    halted = new_ret[~new_ret["tradable"]]
    if len(halted):
        print(
            f"[update] 거래정지(tradable=False): {', '.join(sorted(set(halted['ticker'])))}"
        )
    for w in warnings:
        print(f"[update] 경고: {w}")
    return {"new_days": len(new_dates), "warnings": warnings}


if __name__ == "__main__":
    require_krx_login()
    result = update()
    sys.exit(1 if result["warnings"] else 0)
