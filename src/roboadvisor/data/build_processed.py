"""returns.parquet / features.parquet / benchmark.parquet / dividends.parquet 생성.

    python -m roboadvisor.data.build_processed

A->B 데이터 명세(2~5장, 부록 A.2) 그대로. 날짜 범위는 configs/data.yaml의
fetch_buffer_start부터 받아서 지표·수익률을 계산한 뒤 start_date 이전을 잘라낸다.
KRX_ID/KRX_PW가 환경변수에 있어야 close_krx·벤치마크가 KRX 원본으로 채워진다.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from . import sources

REPO_ROOT = (
    Path(__file__).resolve().parents[3]
)  # src/roboadvisor/data/<이 파일> -> 저장소 루트
ASSETS_YAML = REPO_ROOT / "configs" / "assets.yaml"
DATA_YAML = REPO_ROOT / "configs" / "data.yaml"
OUT_DIR = REPO_ROOT / "data" / "processed"


def load_config() -> tuple[list[dict], dict, dict]:
    assets_cfg = yaml.safe_load(ASSETS_YAML.read_text(encoding="utf-8"))
    data_cfg = yaml.safe_load(DATA_YAML.read_text(encoding="utf-8"))
    return assets_cfg["assets"], assets_cfg["benchmark"], data_cfg


def indicators(px: pd.Series, lr: pd.Series, cfg: dict) -> pd.DataFrame:
    """A->B 명세 부록 A.2 step 5의 공식 그대로."""
    rsi_alpha = 1.0 / cfg["indicators"]["rsi"]["window"]
    fast, slow, signal = (
        cfg["indicators"]["macd"]["fast"],
        cfg["indicators"]["macd"]["slow"],
        cfg["indicators"]["macd"]["signal"],
    )
    vol_window = cfg["indicators"]["volatility"]["window"]

    d = px.diff()
    up = d.clip(lower=0).ewm(alpha=rsi_alpha, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=rsi_alpha, adjust=False).mean()
    rsi = 100 - 100 / (1 + up / dn)
    diff = (
        px.ewm(span=fast, adjust=False).mean() - px.ewm(span=slow, adjust=False).mean()
    )
    macd = (diff - diff.ewm(span=signal, adjust=False).mean()) / px
    vol = lr.rolling(vol_window).std() * np.sqrt(252)
    return pd.DataFrame({"rsi": rsi, "macd": macd, "volatility": vol})


def build_calendar(start: str, end: str) -> tuple[pd.DatetimeIndex, str]:
    bench, tag = sources.fetch_kospi_benchmark(start, end)
    return pd.DatetimeIndex(sorted(pd.to_datetime(bench["date"]).unique())), tag


def build_benchmark(start: str, end: str, calendar: pd.DatetimeIndex) -> pd.DataFrame:
    bench, _tag = sources.fetch_kospi_benchmark(start, end)
    bench["date"] = pd.to_datetime(bench["date"])
    bench = bench.set_index("date").reindex(calendar).ffill()
    bench.index.name = "date"
    return bench.reset_index()


def _align_to_calendar(s: pd.Series, calendar: pd.DatetimeIndex) -> pd.Series:
    s = s.copy()
    s.index = (
        pd.to_datetime(s.index).tz_localize(None)
        if s.index.tz is not None
        else pd.to_datetime(s.index)
    )
    return s.reindex(calendar).ffill()


def build_returns_for_ticker(
    ticker: str, asset_class: str, start: str, end: str, calendar: pd.DatetimeIndex
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """반환: (returns 행, dividends 행, close_krx 행) — close_krx의 source_tag도 같이 돌려준다."""
    px = sources.fetch_naver_adjusted_close(ticker, start, end)
    px = _align_to_calendar(px, calendar)

    is_etf = asset_class != "kr_stock"
    try:
        vol_raw, close_krx_raw, krx_tag = sources.fetch_krx_volume_and_close(
            ticker, start, end, is_etf
        )
        volume = _align_to_calendar(vol_raw, calendar)
        close_krx = _align_to_calendar(close_krx_raw, calendar)
    except Exception as exc:  # noqa: BLE001
        print(
            f"[build] {ticker}: pykrx volume/close failed ({exc}); volume=0 (tradable=False 전체)"
        )
        volume = pd.Series(0.0, index=calendar)
        close_krx = pd.Series(np.nan, index=calendar)
        krx_tag = "unavailable"
    volume = volume.fillna(0.0)
    print(f"[build] {ticker}: close_krx source={krx_tag}")
    close_krx_df = pd.DataFrame(
        {
            "date": calendar,
            "ticker": ticker,
            "close_krx": close_krx.to_numpy(),
            "close_krx_source": krx_tag,
        }
    )

    # 명세 2.1: 주식만 배당 D를 더한다. naver ETF 가격은 분배금이 이미 반영된 수정가라
    # D를 더하면 두 번 센다(2026-10-09 확인: naver/KRX 종가 비율이 배당락일마다
    # 분배금/전일종가만큼 계단식으로 오른다). naver 주식 가격은 KRX 비조정 종가와 같다.
    if asset_class == "kr_stock":
        div = sources.fetch_dividends(ticker)
        div_rows = div.assign(ticker=ticker)[["ticker", "ex_date", "amount", "source"]]
        div_on_calendar = div.set_index("ex_date")["amount"].reindex(
            calendar, fill_value=0.0
        )
    else:
        div_rows = pd.DataFrame(columns=["ticker", "ex_date", "amount", "source"])
        div_on_calendar = pd.Series(0.0, index=calendar)
    simple_return = (px + div_on_calendar) / px.shift(1) - 1.0

    simple_return = simple_return.fillna(0.0)
    simple_return.iloc[0] = 0.0
    log_return = np.log1p(simple_return)
    adj_close = 100.0 * (1.0 + simple_return).cumprod()

    out = pd.DataFrame(
        {
            "date": calendar,
            "ticker": ticker,
            "adj_close": adj_close.to_numpy(),
            "simple_return": simple_return.to_numpy(),
            "log_return": log_return.to_numpy(),
            "volume": volume.to_numpy(),
        }
    )
    out["tradable"] = out["volume"] > 0
    return out, div_rows, close_krx_df


def main() -> None:
    assets, benchmark_cfg, data_cfg = load_config()
    fetch_start = data_cfg["fetch_buffer_start"]
    start_date = data_cfg["start_date"]
    end = pd.Timestamp.today().strftime("%Y-%m-%d")

    calendar_full, kospi_tag = build_calendar(fetch_start, end)
    print(
        f"[build] calendar: {len(calendar_full)} rows, {calendar_full.min().date()}~{calendar_full.max().date()}"
        f" (KOSPI source={kospi_tag})"
    )

    returns_rows, div_rows, close_krx_rows = [], [], []
    for a in assets:
        ticker, asset_class = a["ticker"], a["asset_class"]
        print(f"[build] {ticker} ({a['name']}, {asset_class})")
        r, d, ck = build_returns_for_ticker(
            ticker, asset_class, fetch_start, end, calendar_full
        )
        returns_rows.append(r)
        if not d.empty:
            div_rows.append(d)
        close_krx_rows.append(ck)

    returns_full = pd.concat(returns_rows, ignore_index=True)
    close_krx = pd.concat(close_krx_rows, ignore_index=True)
    returns_full = returns_full.merge(close_krx, on=["date", "ticker"], how="left")

    # adj_close를 fetch_buffer_start(2017-12-01) 기준 100에서 계산해 놓고 자르기만
    # 하면, 명세 §2 "start_date를 100으로 둔다"를 안 지킨다(실측 확인: 2026-10-09
    # 빌드에서 2018-01-02 adj_close가 티커마다 94~112로 제각각이었음 — 전부 워밍업
    # 구간 누적 수익률만큼 어긋난 상수배였다). start_date 행 값으로 다시 나눠
    # 100으로 리베이스한다(버퍼 구간이 남아있는 채로 — 아래서 자른다).
    # start_date 자체가 거래일이 아닐 수 있다(2019-01-01은 휴장일) — "같은 날짜"로
    # anchor를 찾으면 매칭되는 행이 없어 전부 NaN이 된다(실측으로 걸림: 처음엔
    # date==start_ts로 찾다가 KeyError 없이 조용히 빈 Series가 나와서 전체가
    # NaN으로 깨졌었다). start_date **이후 첫 거래일**의 adj_close를 anchor로 쓴다.
    start_ts = pd.Timestamp(start_date)
    on_or_after = returns_full[returns_full["date"] >= start_ts].sort_values("date")
    anchors = on_or_after.groupby("ticker").first()["adj_close"]
    returns_full["adj_close"] = (
        100.0 * returns_full["adj_close"] / returns_full["ticker"].map(anchors)
    )

    # 지표(RSI 14/MACD 26/변동성 20)는 start_date보다 먼저 데이터가 있어야 그 날
    # 이미 워밍업이 끝나 있다. start_date로 자르고 나서 계산하면 start_date 자체가
    # "지표 창의 첫날"이 되어 NaN이 생긴다(2026-10-09 start_date를 2019-01-01로
    # 당겼을 때 실측으로 걸림 — NaN 220개). 그래서 피처는 버퍼가 남아있는
    # returns_full로 계산하고, 최종 출력만 start_date 이후로 자른다.
    feature_rows = []
    for a in assets:
        ticker = a["ticker"]
        sub = returns_full[returns_full["ticker"] == ticker].set_index("date")
        feat = indicators(sub["adj_close"], sub["log_return"], data_cfg)
        feat["date"] = sub.index
        feat["ticker"] = ticker
        feature_rows.append(feat.reset_index(drop=True))
    features_full = pd.concat(feature_rows, ignore_index=True)

    # 이제 start_date 이전(워밍업용으로만 받은 구간)을 둘 다 잘라낸다.
    returns = returns_full[returns_full["date"] >= start_ts].reset_index(drop=True)
    features = features_full[features_full["date"] >= start_ts].reset_index(drop=True)
    features = features[
        ["date", "ticker", "rsi", "macd", "volatility"]
    ]  # 명세 3장 열 순서
    calendar = calendar_full[calendar_full >= start_ts]

    benchmark = build_benchmark(fetch_start, end, calendar_full)
    benchmark = benchmark[benchmark["date"] >= pd.Timestamp(start_date)].reset_index(
        drop=True
    )

    dividends = (
        pd.concat(div_rows, ignore_index=True)
        if div_rows
        else pd.DataFrame(columns=["ticker", "ex_date", "amount", "source"])
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    returns.to_parquet(OUT_DIR / "returns.parquet", index=False)
    features.to_parquet(OUT_DIR / "features.parquet", index=False)
    benchmark.to_parquet(OUT_DIR / "benchmark.parquet", index=False)
    dividends.to_parquet(OUT_DIR / "dividends.parquet", index=False)

    n_tickers = len(assets)
    print(
        f"[build] returns: {len(returns)} rows (expect {len(calendar)}*{n_tickers}={len(calendar)*n_tickers})"
    )
    print(f"[build] features: {len(features)} rows")
    print(f"[build] benchmark: {len(benchmark)} rows")
    print(f"[build] dividends: {len(dividends)} rows")
    print(f"[build] -> {OUT_DIR}")


if __name__ == "__main__":
    main()
