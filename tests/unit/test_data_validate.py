"""No-network unit tests for data/validate.py's check logic.

기존 data/tests는 build_processed/update/dart는 커버하는데, 파이프라인의 최종
품질 게이트인 validate.py 자체의 체크 함수들은 실제 parquet+네트워크로만
돌려봐서 로직 회귀를 pytest로는 못 잡았다. 네트워크가 필요한 체크(naver 재조회)는
fdr.DataReader를 모킹해서, 순수 계산 체크는 합성 데이터로 돌린다.
"""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from roboadvisor.data import validate as v
from roboadvisor.data.build_processed import indicators, load_config

_, _, CFG = load_config()
DATES = pd.bdate_range("2019-01-02", periods=300)


def _price_series(seed: int) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(100 * np.cumprod(1 + rng.normal(0, 0.01, len(DATES))), index=DATES)


def _returns_for(ticker: str, px: pd.Series) -> pd.DataFrame:
    sr = (px / px.shift(1) - 1).fillna(0.0)
    sr.iloc[0] = 0.0
    return pd.DataFrame(
        {
            "date": DATES,
            "ticker": ticker,
            "adj_close": 100 * np.cumprod(1 + sr.to_numpy()),
            "simple_return": sr.to_numpy(),
            "log_return": np.log1p(sr.to_numpy()),
            "volume": 1.0,
            "tradable": True,
            "close_krx": px.to_numpy(),
            "close_krx_source": "krx_unadjusted",
        }
    )


@pytest.fixture(autouse=True)
def _clear_naver_cache():
    v._naver_cache.clear()
    yield
    v._naver_cache.clear()


def test_check_row_count_detects_missing_and_duplicate_rows():
    returns = pd.concat(
        [_returns_for("A", _price_series(0)), _returns_for("B", _price_series(1))],
        ignore_index=True,
    )
    assert v.check_row_count(returns, n_assets=2)
    assert not v.check_row_count(returns.iloc[1:], n_assets=2)
    dup = pd.concat([returns, returns.iloc[[0]]], ignore_index=True)
    assert not v.check_row_count(dup, n_assets=2)


def test_check_no_lookahead_passes_normally_and_fails_on_leaky_indicators():
    returns = _returns_for("005930", _price_series(2))
    cut = str(
        DATES[200].date()
    )  # DATES는 300 영업일 분량이라 이 cut 전후로 과거/미래 둘 다 있어야 한다
    assert v.check_no_lookahead(returns, ticker="005930", cut=cut)

    def leaky_indicators(px, lr, cfg):
        return (
            indicators(px, lr, cfg).shift(-5).bfill()
        )  # 일부러 미래 값을 과거로 끌어옴

    with patch.object(v, "indicators", side_effect=leaky_indicators):
        assert not v.check_no_lookahead(returns, ticker="005930", cut=cut)


def test_check_normalization_stable_passes_normally_and_fails_if_stats_leak_future():
    px = _price_series(3)
    returns = _returns_for("005930", px)
    feat = indicators(
        returns.set_index("date")["adj_close"],
        returns.set_index("date")["log_return"],
        CFG,
    )
    feat = feat.reset_index(drop=True)
    feat["date"] = returns["date"].to_numpy()
    feat["ticker"] = "005930"

    fit_end = str(DATES[150].date())
    assert v.check_normalization_stable(
        returns,
        feat,
        window_id="wtest",
        fit_start=str(DATES[0].date()),
        fit_end=fit_end,
    )

    from roboadvisor.data.preprocessing import fit_normalization_stats

    def leaky_fit(
        features, returns_, **kwargs
    ):  # fit_end 무시 -> 전체 구간으로 통계 계산
        kwargs = {**kwargs, "fit_end": str(DATES[-1].date())}
        return fit_normalization_stats(features, returns_, **kwargs)

    with patch.object(v, "fit_normalization_stats", side_effect=leaky_fit):
        assert not v.check_normalization_stable(
            returns,
            feat,
            window_id="wtest",
            fit_start=str(DATES[0].date()),
            fit_end=fit_end,
        )


def test_check_etf_distributions_counted_once_matches_and_flags_mismatch():
    px = _price_series(4)
    returns = _returns_for("069500", px)
    dividends = pd.DataFrame(columns=["ticker"])
    fake_assets = [
        {"ticker": "069500", "asset_class": "kr_equity"},
        {"ticker": "005930", "asset_class": "kr_stock"},
    ]
    naver_df = pd.DataFrame({"Close": px})

    with (
        patch.object(v, "load_config", return_value=(fake_assets, {}, CFG)),
        patch.object(v.fdr, "DataReader", return_value=naver_df),
    ):
        assert v.check_etf_distributions_counted_once(returns, dividends)

    bumped = naver_df.copy()
    bumped.iloc[-1] *= 1.01  # naver 재조회 값이 저장된 adj_close와 어긋나게 만듦
    v._naver_cache.clear()
    with (
        patch.object(v, "load_config", return_value=(fake_assets, {}, CFG)),
        patch.object(v.fdr, "DataReader", return_value=bumped),
    ):
        assert not v.check_etf_distributions_counted_once(returns, dividends)


def test_last_settled_date_excludes_today_in_kst():
    import datetime
    from zoneinfo import ZoneInfo

    today = pd.Timestamp.now(tz=ZoneInfo("Asia/Seoul")).normalize().tz_localize(None)
    dates = pd.date_range(today - datetime.timedelta(days=5), today, freq="D")
    settled = v._last_settled_date(dates)
    assert settled == today - datetime.timedelta(days=1)


def test_naver_close_is_memoized_per_run():
    calls = []

    def fake_reader(ticker, start, end):
        calls.append((ticker, start, end))
        return pd.DataFrame({"Close": [1.0, 2.0]})

    with patch.object(v.fdr, "DataReader", side_effect=fake_reader):
        v._naver_close("005930", "2020-01-01", "2020-12-31")
        v._naver_close("005930", "2020-01-01", "2020-12-31")
        v._naver_close("000660", "2020-01-01", "2020-12-31")
    assert len(calls) == 2  # 같은 (ticker, start, end) 재조회는 한 번만 실제로 나감
