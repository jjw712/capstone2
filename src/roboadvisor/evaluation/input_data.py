"""C 파트에서 A의 전처리 산출물을 읽고 평가용 날짜를 맞춘다.

수익률은 ``returns.parquet``의 ``simple_return``을 사용한다. ``log_return``은
모델 입력용이며, 성과 지표의 일별 포트폴리오 수익률로 사용하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from roboadvisor.config import get_settings, load_config
from roboadvisor.data.preprocessing import load_processed

RETURN_COLUMNS = {
    "date",
    "ticker",
    "adj_close",
    "simple_return",
    "log_return",
    "volume",
    "tradable",
    "close_krx",
    "close_krx_source",
}
FEATURE_COLUMNS = {"date", "ticker", "rsi", "macd", "volatility"}
BENCHMARK_COLUMNS = {"date", "close", "simple_return"}
DIVIDEND_COLUMNS = {"ticker", "ex_date", "amount", "source"}


@dataclass(frozen=True)
class EvaluationData:
    """A의 원본 행을 보존한, 날짜와 자산 순서가 검증된 평가 입력."""

    returns: pd.DataFrame
    features: pd.DataFrame
    benchmark: pd.DataFrame
    dividends: pd.DataFrame
    assets: tuple[str, ...]

    def test_window(self, window_id: str) -> EvaluationData:
        """실험 설정의 테스트 기간만 선택한다. 학습 기간은 섞지 않는다."""
        windows = load_config("experiments")["walk_forward"]["windows"]
        window = next((w for w in windows if w["id"] == window_id), None)
        if window is None:
            raise ValueError(f"알 수 없는 Walk-Forward 윈도우: {window_id}")
        start, end = (pd.Timestamp(day) for day in window["test"])
        benchmark = self.benchmark.loc[
            self.benchmark["date"].between(start, end)
        ].copy()
        if benchmark.empty:
            raise ValueError(f"{window_id} 테스트 기간에 거래일 데이터가 없습니다")
        dates = benchmark["date"]
        return EvaluationData(
            returns=self.returns.loc[self.returns["date"].isin(dates)].copy(),
            features=self.features.loc[self.features["date"].isin(dates)].copy(),
            benchmark=benchmark,
            dividends=self.dividends.loc[
                self.dividends["ex_date"].between(start, end)
            ].copy(),
            assets=self.assets,
        )


def _require_columns(frame: pd.DataFrame, required: set[str], name: str) -> None:
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"{name}에 필요한 열이 없습니다: {sorted(missing)}")


def _prepare_dates(frame: pd.DataFrame, column: str, name: str) -> pd.DataFrame:
    result = frame.copy()
    result[column] = pd.to_datetime(result[column], errors="raise")
    if result[column].isna().any():
        raise ValueError(f"{name}.{column}에 빈 날짜가 있습니다")
    return result


def _validate_asset_rows(
    frame: pd.DataFrame, name: str, assets: tuple[str, ...]
) -> None:
    if frame.empty:
        raise ValueError(f"{name}에 데이터가 없습니다")
    if frame["ticker"].isna().any():
        raise ValueError(f"{name}.ticker에 빈 값이 있습니다")
    found = set(frame["ticker"])
    if found != set(assets):
        raise ValueError(
            f"{name}의 자산 목록이 assets.yaml과 다릅니다: "
            f"누락={sorted(set(assets) - found)}, 추가={sorted(found - set(assets))}"
        )
    if frame.duplicated(["date", "ticker"]).any():
        raise ValueError(f"{name}에 date/ticker 중복 행이 있습니다")


def _sort_asset_rows(frame: pd.DataFrame, assets: tuple[str, ...]) -> pd.DataFrame:
    order = {ticker: index for index, ticker in enumerate(assets)}
    return (
        frame.assign(_asset_order=frame["ticker"].map(order))
        .sort_values(["date", "_asset_order"])
        .drop(columns="_asset_order")
        .reset_index(drop=True)
    )


def load_evaluation_data(processed_dir: str | Path | None = None) -> EvaluationData:
    """A의 parquet 4종을 읽어 B·C가 공유할 날짜/자산 축을 확인한다.

    첫 거래일의 벤치마크 수익률 NaN은 A의 ``pct_change`` 결과라 허용한다.
    이후 날짜의 결측이나 전략별 날짜 차이는 평가 전에 오류로 알린다.
    """
    directory = Path(processed_dir) if processed_dir else get_settings().processed_dir
    returns, features, benchmark, dividends = load_processed(directory)
    for name, frame, columns in (
        ("returns.parquet", returns, RETURN_COLUMNS),
        ("features.parquet", features, FEATURE_COLUMNS),
        ("benchmark.parquet", benchmark, BENCHMARK_COLUMNS),
        ("dividends.parquet", dividends, DIVIDEND_COLUMNS),
    ):
        _require_columns(frame, columns, name)

    assets = tuple(item["ticker"] for item in load_config("assets")["assets"])
    returns = _prepare_dates(returns, "date", "returns.parquet")
    features = _prepare_dates(features, "date", "features.parquet")
    benchmark = _prepare_dates(benchmark, "date", "benchmark.parquet")
    dividends = _prepare_dates(dividends, "ex_date", "dividends.parquet")

    for name, frame in (("returns.parquet", returns), ("features.parquet", features)):
        _validate_asset_rows(frame, name, assets)
    if benchmark.empty or benchmark.duplicated("date").any():
        raise ValueError("benchmark.parquet가 비어 있거나 날짜가 중복됩니다")

    dates = set(benchmark["date"])
    if set(returns["date"]) != dates:
        raise ValueError("자산 수익률과 KOSPI 벤치마크의 거래일이 다릅니다")
    counts = returns.groupby("date")["ticker"].nunique()
    if not counts.eq(len(assets)).all():
        raise ValueError("일부 거래일에 자산 행이 누락됐습니다")
    return_keys = pd.MultiIndex.from_frame(returns[["date", "ticker"]])
    feature_keys = pd.MultiIndex.from_frame(features[["date", "ticker"]])
    if set(return_keys) != set(feature_keys):
        raise ValueError("returns.parquet와 features.parquet의 date/ticker가 다릅니다")

    if not np.isfinite(
        returns[["adj_close", "simple_return", "log_return"]].to_numpy(dtype=float)
    ).all():
        raise ValueError("returns.parquet의 가격/수익률에 비정상 값이 있습니다")
    if not np.isfinite(
        features[["rsi", "macd", "volatility"]].to_numpy(dtype=float)
    ).all():
        raise ValueError("features.parquet의 피처에 비정상 값이 있습니다")
    benchmark = benchmark.sort_values("date").reset_index(drop=True)
    if (
        not np.isfinite(benchmark["close"].to_numpy(dtype=float)).all()
        or not np.isfinite(
            benchmark["simple_return"].iloc[1:].to_numpy(dtype=float)
        ).all()
    ):
        raise ValueError("benchmark.parquet의 첫 거래일 이후에 비정상 값이 있습니다")

    return EvaluationData(
        returns=_sort_asset_rows(returns, assets),
        features=_sort_asset_rows(features, assets),
        benchmark=benchmark,
        dividends=dividends.sort_values(["ex_date", "ticker"]).reset_index(drop=True),
        assets=assets,
    )
