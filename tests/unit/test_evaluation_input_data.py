"""C의 입력 계층이 A의 실제 parquet 형식과 날짜 축을 지키는지 확인한다."""

from __future__ import annotations

import pandas as pd
import pytest

from roboadvisor.config import load_config
from roboadvisor.evaluation.input_data import load_evaluation_data


@pytest.fixture
def a_output(tmp_path):
    assets = [item["ticker"] for item in load_config("assets")["assets"]]
    dates = pd.to_datetime(["2022-12-29", "2023-01-02", "2023-01-03"])
    rows = [(day, ticker) for day in dates for ticker in reversed(assets)]
    returns = pd.DataFrame(
        [
            {
                "date": day,
                "ticker": ticker,
                "adj_close": 100.0 + index,
                "simple_return": 0.01,
                "log_return": 0.00995,
                "volume": 1000.0,
                "tradable": True,
                "close_krx": 100.0,
                "close_krx_source": "krx_unadjusted",
            }
            for index, (day, ticker) in enumerate(rows)
        ]
    )
    features = returns[["date", "ticker"]].assign(rsi=50.0, macd=0.01, volatility=0.2)
    benchmark = pd.DataFrame(
        {
            "date": dates,
            "close": [2300.0, 2310.0, 2320.0],
            "simple_return": [float("nan"), 0.004, 0.0043],
        }
    )
    dividends = pd.DataFrame(
        {
            "ticker": [assets[0]],
            "ex_date": pd.to_datetime(["2023-01-02"]),
            "amount": [100.0],
            "source": ["yahoo"],
        }
    )
    for name, frame in (
        ("returns", returns),
        ("features", features),
        ("benchmark", benchmark),
        ("dividends", dividends),
    ):
        frame.to_parquet(tmp_path / f"{name}.parquet", index=False)
    return tmp_path, assets


def test_loads_a_outputs_and_selects_test_window(a_output):
    directory, assets = a_output
    data = load_evaluation_data(directory)
    assert data.assets == tuple(assets)
    assert data.returns.loc[: len(assets) - 1, "ticker"].tolist() == assets
    assert pd.isna(data.benchmark.loc[0, "simple_return"])

    window = data.test_window("w1")
    assert window.benchmark["date"].dt.year.eq(2023).all()
    assert len(window.returns) == 2 * len(assets)
    assert len(window.dividends) == 1


def test_rejects_missing_asset_day(a_output):
    directory, _ = a_output
    path = directory / "returns.parquet"
    returns = pd.read_parquet(path)
    returns.iloc[1:].to_parquet(path, index=False)
    with pytest.raises(ValueError, match="자산 행이 누락"):
        load_evaluation_data(directory)


def test_rejects_misaligned_features(a_output):
    directory, _ = a_output
    path = directory / "features.parquet"
    features = pd.read_parquet(path)
    features.iloc[1:].to_parquet(path, index=False)
    with pytest.raises(ValueError, match="date/ticker가 다릅니다"):
        load_evaluation_data(directory)


def test_rejects_benchmark_gap_after_first_day(a_output):
    directory, _ = a_output
    path = directory / "benchmark.parquet"
    benchmark = pd.read_parquet(path)
    benchmark.loc[1, "simple_return"] = float("nan")
    benchmark.to_parquet(path, index=False)
    with pytest.raises(ValueError, match="첫 거래일 이후에 비정상 값"):
        load_evaluation_data(directory)
