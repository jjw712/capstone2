"""No-network unit tests for the A-side data pipeline (indicators + normalization)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from roboadvisor.data.build_processed import indicators, load_config
from roboadvisor.data.preprocessing import fit_normalization_stats


def test_assets_yaml_has_11_assets_in_spec_order():
    assets, benchmark, _ = load_config()
    assert len(assets) == 11
    assert [a["ticker"] for a in assets][:3] == ["005930", "000660", "035420"]
    assert all(isinstance(a["ticker"], str) for a in assets)  # no octal-int bug
    assert benchmark["ticker"] == "1001"


def test_indicators_rsi_bounds_and_macd_shape():
    rng = np.random.default_rng(0)
    px = pd.Series(100 * np.cumprod(1 + rng.normal(0, 0.01, 300)))
    lr = np.log1p(px.pct_change().fillna(0.0))
    cfg = {
        "indicators": {
            "rsi": {"window": 14},
            "macd": {"fast": 12, "slow": 26, "signal": 9},
            "volatility": {"window": 20},
        }
    }
    out = indicators(px, lr, cfg)
    assert set(out.columns) == {"rsi", "macd", "volatility"}
    valid_rsi = out["rsi"].dropna()
    assert (valid_rsi >= 0).all() and (valid_rsi <= 100).all()
    assert len(out) == len(px)


def test_indicators_constant_price_gives_neutral_rsi():
    # No ups or downs -> up/dn both 0 -> rsi undefined (NaN), not a crash.
    px = pd.Series([100.0] * 50)
    lr = pd.Series([0.0] * 50)
    cfg = {
        "indicators": {
            "rsi": {"window": 14},
            "macd": {"fast": 12, "slow": 26, "signal": 9},
            "volatility": {"window": 20},
        }
    }
    out = indicators(px, lr, cfg)
    assert out["macd"].iloc[-1] == pytest.approx(0.0)
    assert out["volatility"].iloc[-1] == pytest.approx(0.0)


def test_fit_normalization_stats_shape_and_split():
    dates = pd.date_range("2020-01-01", periods=40, freq="B")
    rng = np.random.default_rng(1)
    rows_r, rows_f = [], []
    for t in ["A", "B"]:
        lr = rng.normal(0, 0.01, len(dates))
        rows_r.append(pd.DataFrame({"date": dates, "ticker": t, "log_return": lr}))
        rows_f.append(
            pd.DataFrame(
                {
                    "date": dates,
                    "ticker": t,
                    "rsi": rng.uniform(0, 100, len(dates)),
                    "macd": rng.normal(0, 0.01, len(dates)),
                    "volatility": rng.uniform(0.05, 0.3, len(dates)),
                }
            )
        )
    returns = pd.concat(rows_r, ignore_index=True)
    features = pd.concat(rows_f, ignore_index=True)

    stats = fit_normalization_stats(
        features,
        returns,
        window_id="wtest",
        fit_start=str(dates[0].date()),
        fit_end=str(dates[20].date()),
    )
    assert len(stats) == 2 + 3  # 2 tickers (log_return) + 3 pooled features
    log_ret_rows = stats[stats.feature == "log_return"]
    assert set(log_ret_rows["ticker"]) == {"A", "B"}
    assert (log_ret_rows["mean"] == 0.0).all()  # mean fixed at 0, never demeaned
    pooled_rows = stats[stats.feature != "log_return"]
    assert (pooled_rows["ticker"] == "*").all()
    assert not stats[["mean", "std"]].isna().any().any()


def test_normalization_log_return_rows_follow_assets_yaml_order():
    dates = pd.date_range("2020-01-01", periods=30, freq="B")
    rng = np.random.default_rng(2)
    tickers = [
        "105560",
        "ZZZ",
        "005930",
    ]  # 일부러 뒤섞고, assets.yaml에 없는 티커도 섞음
    returns = pd.concat(
        [
            pd.DataFrame(
                {
                    "date": dates,
                    "ticker": t,
                    "log_return": rng.normal(0, 0.01, len(dates)),
                }
            )
            for t in tickers
        ],
        ignore_index=True,
    )
    features = pd.concat(
        [
            pd.DataFrame(
                {
                    "date": dates,
                    "ticker": t,
                    "rsi": 50.0,
                    "macd": 0.0,
                    "volatility": 0.2,
                }
            )
            for t in tickers
        ],
        ignore_index=True,
    )
    stats = fit_normalization_stats(
        features, returns, window_id="w", fit_start="2020-01-01", fit_end="2020-02-11"
    )
    assert list(stats[stats.feature == "log_return"]["ticker"]) == [
        "005930",
        "105560",
        "ZZZ",
    ]
