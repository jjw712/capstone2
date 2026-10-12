"""data/update.py 증분 갱신 — 네트워크 없이 원천 호출을 가짜로 바꿔 검증."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd

from roboadvisor.data import update as upd
from roboadvisor.data.build_processed import indicators, load_config

_, _, CFG = load_config()
TICKER = "005930"
DATES = pd.bdate_range("2024-01-02", periods=80)
PRICE = pd.Series(
    100 * np.exp(np.cumsum(np.random.default_rng(3).normal(0, 0.01, len(DATES)))),
    index=DATES,
)


def fake_build(ticker, asset_class, start, end, calendar):
    px = PRICE.reindex(calendar)
    sr = (px / px.shift(1) - 1).fillna(0.0)
    r = pd.DataFrame(
        {
            "date": calendar,
            "ticker": ticker,
            "adj_close": 0.0,
            "simple_return": sr.to_numpy(),
            "log_return": np.log1p(sr.to_numpy()),
            "volume": 1.0,
            "tradable": True,
        }
    )
    ck = pd.DataFrame(
        {
            "date": calendar,
            "ticker": ticker,
            "close_krx": px.to_numpy(),
            "close_krx_source": "krx_unadjusted",
        }
    )
    return r, pd.DataFrame(columns=["ticker", "ex_date", "amount", "source"]), ck


def fake_bench(start, end):
    close = PRICE * 10
    return (
        pd.DataFrame(
            {
                "date": DATES,
                "close": close.to_numpy(),
                "simple_return": close.pct_change().to_numpy(),
            }
        ),
        "fake",
    )


def write_saved(tmp, n_saved, tamper=False):
    r, _, ck = fake_build(TICKER, "kr_stock", None, None, DATES[:n_saved])
    r = r.merge(ck, on=["date", "ticker"])
    r["adj_close"] = 100 * np.cumprod(1 + r["simple_return"].to_numpy())
    if tamper:
        r.loc[n_saved - 2, "simple_return"] += 0.01
    f = indicators(
        r.set_index("date")["adj_close"], r.set_index("date")["log_return"], CFG
    ).reset_index()
    f.insert(1, "ticker", TICKER)
    b, _ = fake_bench(None, None)
    r.to_parquet(tmp / "returns.parquet", index=False)
    f.to_parquet(tmp / "features.parquet", index=False)
    b.iloc[:n_saved].to_parquet(tmp / "benchmark.parquet", index=False)
    pd.DataFrame(
        {
            "ticker": pd.Series(dtype=str),
            "ex_date": pd.Series(dtype="datetime64[ns]"),
            "amount": pd.Series(dtype=float),
            "source": pd.Series(dtype=str),
        }
    ).to_parquet(tmp / "dividends.parquet", index=False)


def run_update(tmp):
    assets = [{"ticker": TICKER, "asset_class": "kr_stock"}]
    with (
        patch.object(upd, "load_config", return_value=(assets, {}, CFG)),
        patch.object(upd, "build_returns_for_ticker", side_effect=fake_build),
        patch.object(upd.sources, "fetch_kospi_benchmark", side_effect=fake_bench),
    ):
        return upd.update(tmp, end="2024-12-31")


def test_update_continues_adj_close_and_matches_full_computation(tmp_path):
    write_saved(tmp_path, 60)
    res = run_update(tmp_path)
    assert res["new_days"] == 20 and res["warnings"] == []
    out = pd.read_parquet(tmp_path / "returns.parquet")
    expected = 100 * np.cumprod(1 + PRICE.pct_change().fillna(0).to_numpy())
    assert np.allclose(out["adj_close"].to_numpy(), expected)
    feat = pd.read_parquet(tmp_path / "features.parquet")
    full = indicators(
        pd.Series(expected, index=DATES), out.set_index("date")["log_return"], CFG
    )
    assert np.allclose(
        feat[["rsi", "macd", "volatility"]].to_numpy(), full.to_numpy(), equal_nan=True
    )
    assert len(pd.read_parquet(tmp_path / "benchmark.parquet")) == 80


def test_update_warns_when_overlap_return_differs_from_saved(tmp_path):
    write_saved(tmp_path, 60, tamper=True)
    res = run_update(tmp_path)
    assert any(TICKER in w and "수익률" in w for w in res["warnings"])


def test_update_noop_when_already_latest(tmp_path):
    write_saved(tmp_path, 80)
    assert run_update(tmp_path)["new_days"] == 0
