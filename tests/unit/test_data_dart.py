"""No-network tests for DART alotMatter parsing (data/dart.py).

Fixtures mirror real 2026-10-09 API responses (field names, "se" spacing,
stock_knd quirks) rather than invented shapes.
"""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from roboadvisor.data.dart import (
    fetch_dividend_disclosure,
    fiscal_year_of_decision,
    is_own_dividend_decision,
    match_events,
)


def test_decision_filter_keeps_only_own_original_disclosures():
    # report_nm values copied from real list.json responses (2026-10-09).
    assert is_own_dividend_decision("현금ㆍ현물배당결정               ")
    assert not is_own_dividend_decision("[기재정정]현금ㆍ현물배당결정")
    assert not is_own_dividend_decision("현금ㆍ현물배당결정(자회사의 주요경영사항)")
    assert not is_own_dividend_decision("현금ㆍ현물배당을위한주주명부폐쇄(기준일)결정")


def test_fiscal_year_of_decision():
    assert fiscal_year_of_decision(pd.Timestamp("2025-01-23")) == 2024  # 결산배당
    assert (
        fiscal_year_of_decision(pd.Timestamp("2024-02-07")) == 2023
    )  # 기준일 개편 후 결산배당
    assert fiscal_year_of_decision(pd.Timestamp("2025-04-24")) == 2025  # 1분기 배당


def test_match_events_one_to_one_both_directions_and_orphans():
    events = pd.DataFrame(
        {
            "ex_date": pd.to_datetime(["2023-12-27", "2024-02-28", "2024-06-27"]),
            "amount": [361.0, 1530.0, 791.0],
        }
    )
    decisions = pd.DataFrame(
        {
            "rcept_no": ["A", "B", "C", "D"],
            "decision_date": pd.to_datetime(
                ["2024-01-31", "2024-02-07", "2024-07-23", "2025-10-30"]
            ),
        }
    )
    matched, orphans = match_events(events, decisions)
    assert list(matched["rcept_no"]) == ["A", "B", "C"]
    assert list(matched["days_ex_to_decision"]) == [35, -21, 26]
    assert list(orphans["rcept_no"]) == ["D"]


def test_match_events_leaves_event_without_nearby_decision_unmatched():
    events = pd.DataFrame(
        {"ex_date": pd.to_datetime(["2020-03-30"]), "amount": [100.0]}
    )
    decisions = pd.DataFrame(
        {"rcept_no": ["X"], "decision_date": pd.to_datetime(["2021-01-01"])}
    )
    matched, orphans = match_events(events, decisions)
    assert matched["rcept_no"].isna().all()
    assert list(orphans["rcept_no"]) == ["X"]


def _resp(list_rows):
    return {"status": "000", "message": "정상", "list": list_rows}


def test_parses_common_stock_row_with_space_in_se():
    # Real Samsung 2023 shape: se has a space, stock_knd distinguishes common/preferred.
    rows = _resp(
        [
            {"se": "주당 현금배당금(원)", "stock_knd": "보통주", "thstrm": "1,444"},
            {"se": "주당 현금배당금(원)", "stock_knd": "우선주", "thstrm": "1,445"},
        ]
    )
    with patch("roboadvisor.data.dart.requests.get") as m:
        m.return_value.json.return_value = rows
        m.return_value.raise_for_status.return_value = None
        out = fetch_dividend_disclosure("00126380", 2023, api_key="x")
    assert out["per_share_cash_dividend"] == 1444.0


def test_falls_back_to_dash_stock_knd_when_no_class_split():
    # Real SK Hynix 2019/2020 shape: stock_knd is "-", not "보통주" (no preferred
    # class disclosed that way) -- this was the actual bug found 2026-10-09.
    rows = _resp(
        [
            {"se": "주당 현금배당금(원)", "stock_knd": "-", "thstrm": "1,000"},
            {"se": "주당 현금배당금(원)", "stock_knd": "-", "thstrm": "-"},
        ]
    )
    with patch("roboadvisor.data.dart.requests.get") as m:
        m.return_value.json.return_value = rows
        m.return_value.raise_for_status.return_value = None
        out = fetch_dividend_disclosure("00164779", 2019, api_key="x")
    assert out["per_share_cash_dividend"] == 1000.0


def test_prefers_common_stock_over_dash_when_both_present():
    rows = _resp(
        [
            {"se": "주당 현금배당금(원)", "stock_knd": "-", "thstrm": "9,999"},
            {"se": "주당 현금배당금(원)", "stock_knd": "보통주", "thstrm": "1,444"},
        ]
    )
    with patch("roboadvisor.data.dart.requests.get") as m:
        m.return_value.json.return_value = rows
        m.return_value.raise_for_status.return_value = None
        out = fetch_dividend_disclosure("00126380", 2023, api_key="x")
    assert out["per_share_cash_dividend"] == 1444.0


def test_returns_none_when_status_not_ok():
    with patch("roboadvisor.data.dart.requests.get") as m:
        m.return_value.json.return_value = {"status": "013", "message": "no data"}
        m.return_value.raise_for_status.return_value = None
        out = fetch_dividend_disclosure("00126380", 1999, api_key="x")
    assert out is None


def test_ignores_dash_value_rows():
    rows = _resp(
        [
            {"se": "주당 현금배당금(원)", "stock_knd": "보통주", "thstrm": "-"},
        ]
    )
    with patch("roboadvisor.data.dart.requests.get") as m:
        m.return_value.json.return_value = rows
        m.return_value.raise_for_status.return_value = None
        out = fetch_dividend_disclosure("00126380", 2023, api_key="x")
    assert out["per_share_cash_dividend"] is None
