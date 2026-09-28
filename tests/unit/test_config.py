"""설정 파일 로드와 명세 고정값 확인. 명세 값을 잘못 바꾸면 여기서 실패한다."""

from datetime import date

import pytest

from roboadvisor.config import CONFIG_DIR, load_config

CONFIG_NAMES = sorted(p.stem for p in CONFIG_DIR.glob("*.yaml"))


@pytest.mark.parametrize("name", CONFIG_NAMES)
def test_every_config_loads(name):
    assert isinstance(load_config(name), dict)


def test_assets_are_ten_or_more_and_unique():
    tickers = [a["ticker"] for a in load_config("assets")["assets"]]
    assert len(tickers) >= 10
    assert len(set(tickers)) == len(tickers)


def test_trading_costs_and_safeguard_match_spec():
    cfg = load_config("trading")
    assert cfg["costs"]["fee_rate"] == 0.00015
    assert cfg["costs"]["slippage_rate"] == 0.0005
    assert cfg["safeguard"]["max_drawdown"] == 0.15


def test_rl_settings_within_spec():
    cfg = load_config("rl")
    assert 20 <= cfg["observation"]["window"] <= 60
    assert cfg["ppo"]["total_timesteps"] >= 100_000
    assert set(cfg["reward"]["variants"]) == {"simple", "sharpe", "mdd_penalty"}


def test_walk_forward_trains_four_years_and_tests_one():
    windows = load_config("experiments")["walk_forward"]["windows"]
    assert len(windows) >= 2
    for w in windows:
        train_start, train_end = (date.fromisoformat(d) for d in w["train"])
        test_start, test_end = (date.fromisoformat(d) for d in w["test"])
        assert train_end.year - train_start.year + 1 == 4
        assert test_start > train_end
        assert test_start.year == test_end.year


def test_lambda_grid_within_spec_range():
    grid = load_config("experiments")["lambda_grid"]
    assert grid and all(0.5 <= lam <= 5.0 for lam in grid)


def test_mvo_constraints_match_spec():
    mvo = load_config("baselines")["mvo"]
    assert mvo["cov_lookback_days"] == 252
    assert mvo["max_weight"] == 0.40
    assert mvo["long_only"] is True


def test_news_crawling_rules_match_spec():
    cfg = load_config("research")["collection"]
    assert cfg["min_request_interval_sec"] >= 1.0
    assert cfg["summary_max_chars"] <= 300
    assert cfg["respect_robots_txt"] is True
