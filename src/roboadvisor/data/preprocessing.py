"""정규화 통계 — A->B 데이터 명세 6장.

B는 학습 구간(윈도우)마다 ``fit_normalization_stats``를 불러 통계를 받고, 학습한
모델 파일과 함께 저장한다. 서비스할 때도 같은 통계를 다시 써야 한다(학습 밖 구간
정보가 섞이면 안 됨 — look-ahead 금지).

계산 구간: 그 윈도우의 train_start ~ (val_start 하루 전)까지. `configs/experiments.yaml`
의 ``fit_start``/``fit_end``가 이미 이 구간으로 잘려 있다(= train에서 val 6개월을 뺀
구간, 명세서 예시: w1 = 2019-01-02 ~ 2022-06-30).

결과 형식: log_return은 자산별로 평균 0(빼지 않음)·표준편차만 자산별 계산,
rsi/macd/volatility는 11개 자산을 합쳐 하나의 평균·표준편차(ticker="*")로 계산한다
(명세 §6 "이렇게 나누는 이유" — 수익률은 자산 간 스케일을 맞추고, 변동성류는
"채권이 주식보다 덜 흔들린다"는 수준 차이를 남겨 두기 위함).

적용((x-mean)/std)과 ±5 클리핑은 B(관측 생성) 몫이다 — 여기서는 통계만 만든다.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

FEATURES_NOT_DEMEANED = {"log_return"}  # mean=0 고정 (명세 표 그대로)
ASSETS_YAML = (
    Path(__file__).resolve().parents[3] / "configs" / "assets.yaml"
)  # src/roboadvisor/data/ -> 저장소 루트


def _asset_order(tickers: pd.Series) -> list[str]:
    order = [
        a["ticker"]
        for a in yaml.safe_load(ASSETS_YAML.read_text(encoding="utf-8"))["assets"]
    ]
    present = set(tickers)
    return [t for t in order if t in present] + sorted(present - set(order))


def fit_normalization_stats(
    features: pd.DataFrame,
    returns: pd.DataFrame,
    *,
    window_id: str,
    fit_start: str,
    fit_end: str,
    pooled_features: tuple[str, ...] = ("rsi", "macd", "volatility"),
) -> pd.DataFrame:
    """학습 구간(fit_start~fit_end)의 평균·표준편차를 명세 §6 형식으로 반환.

    반환 컬럼: window_id, fit_start, fit_end, feature, ticker, mean, std.
    `ticker` 는 log_return에서는 자산 코드, pooled_features에서는 ``"*"``.
    """
    fit_start_ts, fit_end_ts = pd.Timestamp(fit_start), pd.Timestamp(fit_end)
    feat = features.copy()
    feat["date"] = pd.to_datetime(feat["date"])
    feat = feat[(feat["date"] >= fit_start_ts) & (feat["date"] <= fit_end_ts)]

    ret = returns.copy()
    ret["date"] = pd.to_datetime(ret["date"])
    ret = ret[(ret["date"] >= fit_start_ts) & (ret["date"] <= fit_end_ts)]

    rows: list[dict] = []

    # log_return: 자산별, 평균 0 고정, 표준편차만 자산별. 행 순서는 명세 1.1대로 assets.yaml 순서.
    for ticker in _asset_order(ret["ticker"]):
        grp = ret[ret["ticker"] == ticker]
        rows.append(
            {
                "window_id": window_id,
                "fit_start": fit_start,
                "fit_end": fit_end,
                "feature": "log_return",
                "ticker": ticker,
                "mean": 0.0,
                "std": float(grp["log_return"].std()),
            }
        )

    # rsi/macd/volatility: 11개 자산 통합 1행.
    for f in pooled_features:
        pooled = feat[f].dropna()
        rows.append(
            {
                "window_id": window_id,
                "fit_start": fit_start,
                "fit_end": fit_end,
                "feature": f,
                "ticker": "*",
                "mean": float(pooled.mean()),
                "std": float(pooled.std()),
            }
        )

    return pd.DataFrame(rows)


def load_processed(
    processed_dir: str | Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """returns/features/benchmark/dividends parquet 4개를 읽어 반환."""
    d = Path(processed_dir)
    returns = pd.read_parquet(d / "returns.parquet")
    features = pd.read_parquet(d / "features.parquet")
    benchmark = pd.read_parquet(d / "benchmark.parquet")
    dividends = pd.read_parquet(d / "dividends.parquet")
    return returns, features, benchmark, dividends
