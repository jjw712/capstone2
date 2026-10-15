"""OpenDART 공시로 yfinance 배당 기록을 건별로 대조한다 (명세 5장, 부록 A.1·A.3).

    set -a; source .env; set +a
    python -m roboadvisor.data.dart

키는 환경변수(DART_API_KEY)로만 받는다.

절차:
    1. list.json으로 종목별 '현금ㆍ현물배당결정' 공시 목록을 받는다(정정공시·자회사 공시 제외).
    2. 야후 배당 한 건마다 가장 가까운 결정공시 한 건을 1:1로 짝짓는다. 짝이 없는
       야후 배당(유령 배당)이나 짝이 없는 결정공시(누락 배당)를 찾아낸다.
    3. 짝지은 결정공시의 날짜로 사업연도를 정해, 사업연도별 야후 합계를
       alotMatter(사업보고서 '배당에 관한 사항')의 주당 현금배당금과 비교한다.

공시 원문(document.xml)을 읽으면 건별 금액·배당기준일까지 볼 수 있지만, 2026-10-09
현재 그 엔드포인트는 "800 시스템 점검"이다. DART 웹 뷰어는 robots.txt가 막고 있어
쓰지 않는다. 그래서 금액은 사업연도 합계로, 날짜는 결정공시와의 간격으로만 확인한다.
"""

from __future__ import annotations

import io
import os
import re
import time
import zipfile
from pathlib import Path

import pandas as pd
import requests

DART_BASE = "https://opendart.fss.or.kr/api"
# 코드는 src/roboadvisor/data/에 있지만 실제 산출물은 저장소 루트의 data/processed/에 둔다
# (data/는 .gitignore로 코드를 안 받는 전용 폴더라 코드와 같은 자리에 둘 수 없다).
PROCESSED_DIR = Path(__file__).resolve().parents[3] / "data" / "processed"
CORP_CODE_CACHE = PROCESSED_DIR / "_dart_corp_codes.parquet"
KR_STOCK_TICKERS = ["005930", "000660", "035420", "005380", "105560"]
MIN_INTERVAL_SEC = 1.0  # 명세 A.3 / 미션 제약: 초당 1회 이하
EVENTS_SINCE = "2017-12-01"  # configs/data.yaml fetch_buffer_start — 수익률 계산에 쓰이는 배당 전부
MATCH_MAX_DAYS = 100


def _require_key() -> str:
    key = os.getenv("DART_API_KEY")
    if not key:
        raise RuntimeError("DART_API_KEY not set — export it, do not hardcode it")
    return key


def _get(url: str, params: dict, timeout: int = 30) -> requests.Response:
    """DART 서버가 가끔 읽기 시간 초과를 낸다(2026-10-09 실측). 3번까지 다시 시도한다."""
    for attempt in range(3):
        try:
            return requests.get(url, params=params, timeout=timeout)
        except (requests.ConnectionError, requests.Timeout):
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))


# 2026-10-09 실측: corpCode.xml(전체 상장사 ZIP) 엔드포인트가 "800 시스템 점검"으로
# 막혀 있었다(같은 키로 company.json은 정상 응답 — 키 문제가 아니라 그 엔드포인트만
# 점검 중). 5종목만 필요해서, 후보 corp_code를 company.json으로 하나씩 호출해
# stock_code가 실제로 일치하는지 그 자리에서 확인하는 방식으로 우회했다 — 추측값을
# 그냥 믿은 게 아니라 전부 DART 응답으로 검증됨(아래 4개 전부 MATCH 확인).
_VERIFIED_CORP_CODES = {
    "005930": "00126380",  # 삼성전자(주) — company.json으로 직접 확인
    "000660": "00164779",  # 에스케이하이닉스(주) — company.json으로 직접 확인
    "035420": "00266961",  # 네이버(주) — company.json으로 직접 확인
    "005380": "00164742",  # 현대자동차(주) — company.json으로 직접 확인
    "105560": "00688996",  # (주)KB금융지주 — company.json으로 직접 확인
}


def fetch_corp_code_map(
    api_key: str | None = None, force: bool = False
) -> pd.DataFrame:
    """stock_code -> corp_code, corp_name 매핑.

    전체 ZIP(corpCode.xml)이 되면 그걸 쓰고, 안 되면(2026-10-09 기준 점검 중)
    _VERIFIED_CORP_CODES로 폴백한다 — 둘 다 "추측 아님, API로 확인됨"이 원칙.
    """
    if not force and CORP_CODE_CACHE.is_file():
        return pd.read_parquet(CORP_CODE_CACHE)

    api_key = api_key or _require_key()
    try:
        resp = requests.get(
            f"{DART_BASE}/corpCode.xml", params={"crtfc_key": api_key}, timeout=30
        )
        resp.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            xml_bytes = zf.read(zf.namelist()[0])
        text = xml_bytes.decode("utf-8")
        rows = []
        for block in re.findall(r"<list>(.*?)</list>", text, re.S):

            def _field(tag: str) -> str:
                m = re.search(rf"<{tag}>(.*?)</{tag}>", block, re.S)
                return m.group(1).strip() if m else ""

            stock_code = _field("stock_code")
            if not stock_code:
                continue
            rows.append(
                {
                    "stock_code": stock_code,
                    "corp_code": _field("corp_code"),
                    "corp_name": _field("corp_name"),
                }
            )
        df = pd.DataFrame(rows)
    except (requests.HTTPError, zipfile.BadZipFile) as exc:
        print(
            f"[dart] corpCode.xml unavailable ({exc}); using verified fallback map for {len(_VERIFIED_CORP_CODES)} tickers"
        )
        rows = []
        for stock_code, corp_code in _VERIFIED_CORP_CODES.items():
            r = requests.get(
                f"{DART_BASE}/company.json",
                params={"crtfc_key": api_key, "corp_code": corp_code},
                timeout=20,
            )
            j = r.json()
            rows.append(
                {
                    "stock_code": stock_code,
                    "corp_code": corp_code,
                    "corp_name": j.get("corp_name", ""),
                }
            )
            time.sleep(MIN_INTERVAL_SEC)
        df = pd.DataFrame(rows)

    CORP_CODE_CACHE.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(CORP_CODE_CACHE, index=False)
    return df


def fetch_dividend_disclosure(
    corp_code: str, year: int, api_key: str | None = None
) -> dict | None:
    """alotMatter.json(배당에 관한 사항) — 사업연도 year의 주당 현금배당금(보통주)."""
    api_key = api_key or _require_key()
    time.sleep(MIN_INTERVAL_SEC)
    resp = _get(
        f"{DART_BASE}/alotMatter.json",
        params={
            "crtfc_key": api_key,
            "corp_code": corp_code,
            "bsns_year": str(year),
            "reprt_code": "11011",  # 사업보고서(연간)
        },
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "000":
        return None  # 013(no data) 등 — 공시가 없는 해는 조용히 스킵

    # 실제 응답 확인(2026-10-09, 삼성전자 2023): se="주당 현금배당금(원)"(공백 있음),
    # 보통주/우선주 구분은 se가 아니라 별도 stock_knd 필드다. se.replace(" ","")로
    # 공백 유무를 흡수한다.
    # 2019/2020년 SK하이닉스 공시는 stock_knd가 "보통주"가 아니라 "-"였다(우선주
    # 구분 없이 공시) — 그래서 "보통주"만 찾으면 실제로 있는 값을 놓친다.
    # "보통주" 우선, 없으면 유일하게 남는 "-" 행으로 폴백한다(그 경우 그 행이
    # 사실상 전체 주식의 배당금이라는 뜻).
    candidates = [
        row
        for row in data.get("list", [])
        if (row.get("se") or "").replace(" ", "") == "주당현금배당금(원)"
    ]
    per_share = None
    for stock_knd_wanted in ("보통주", "-"):
        for row in candidates:
            if (row.get("stock_knd") or "").strip() != stock_knd_wanted:
                continue
            raw = (row.get("thstrm") or "").replace(",", "").strip()
            if raw and raw not in {"-", ""}:
                try:
                    per_share = float(raw)
                except ValueError:
                    continue
                break
        if per_share is not None:
            break
    return {"year": year, "per_share_cash_dividend": per_share, "raw": data.get("list")}


def is_own_dividend_decision(report_nm: str) -> bool:
    """본사 '현금ㆍ현물배당결정' 원공시만. 정정공시·자회사 공시·기준일 공시는 뺀다.

    실측(2026-10-09): KB금융은 '현금ㆍ현물배당결정(자회사의 주요경영사항)'이 본사 공시와
    거의 같은 수로 섞여 있고, 정정공시는 '[기재정정]' 접두어로 같은 배당을 한 번 더 올린다.
    """
    name = re.sub(r"\s+", "", report_nm)
    return name == "현금ㆍ현물배당결정"


def fetch_dividend_decisions(
    corp_code: str,
    bgn: str = "20170901",
    end: str | None = None,
    api_key: str | None = None,
) -> pd.DataFrame:
    api_key = api_key or _require_key()
    end = end or pd.Timestamp.today().strftime("%Y%m%d")
    rows, page = [], 1
    while True:
        time.sleep(MIN_INTERVAL_SEC)
        j = _get(
            f"{DART_BASE}/list.json",
            params={
                "crtfc_key": api_key,
                "corp_code": corp_code,
                "bgn_de": bgn,
                "end_de": end,
                "pblntf_ty": "I",
                "page_no": page,
                "page_count": 100,
            },
            timeout=30,
        ).json()
        if j.get("status") == "013":
            break
        if j.get("status") != "000":
            raise RuntimeError(
                f"DART list.json status={j.get('status')} {j.get('message')}"
            )
        rows += [r for r in j["list"] if is_own_dividend_decision(r["report_nm"])]
        if page >= int(j["total_page"]):
            break
        page += 1
    df = pd.DataFrame(rows, columns=["rcept_no", "rcept_dt", "report_nm"])
    df["decision_date"] = pd.to_datetime(df["rcept_dt"], format="%Y%m%d")
    return (
        df[["rcept_no", "decision_date"]]
        .sort_values("decision_date")
        .reset_index(drop=True)
    )


def fiscal_year_of_decision(decision_date: pd.Timestamp) -> int:
    """1~3월 결정은 직전 사업연도의 결산배당, 4월 이후는 그 해의 분기·중간배당."""
    return decision_date.year - 1 if decision_date.month <= 3 else decision_date.year


def match_events(
    events: pd.DataFrame, decisions: pd.DataFrame, max_days: int = MATCH_MAX_DAYS
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """야후 배당(ex_date, amount)과 결정공시(rcept_no, decision_date)를 날짜가 가까운 순으로 1:1 매칭.

    분기말 기준일 회사(삼성전자 등)는 배당락 뒤 약 한 달 뒤에 결정공시가 나오고, 2023년 제도
    개편 뒤 기준일을 뒤로 미룬 회사(KB금융 등)는 결정공시가 배당락보다 먼저 나온다. 그래서
    방향을 정하지 않고 절대 일수로 가까운 것부터 짝짓는다.
    """
    pairs = []
    for i, ev in events.iterrows():
        for j, dc in decisions.iterrows():
            days = (dc["decision_date"] - ev["ex_date"]).days
            if abs(days) <= max_days:
                pairs.append((abs(days), i, j, days))
    pairs.sort()
    used_e, used_d, out = set(), set(), []
    for _, i, j, days in pairs:
        if i in used_e or j in used_d:
            continue
        used_e.add(i)
        used_d.add(j)
        dc = decisions.loc[j]
        out.append(
            {
                "event_idx": i,
                "rcept_no": dc["rcept_no"],
                "decision_date": dc["decision_date"],
                "days_ex_to_decision": days,
                "fiscal_year": fiscal_year_of_decision(dc["decision_date"]),
            }
        )
    matched = pd.DataFrame(
        out,
        columns=[
            "event_idx",
            "rcept_no",
            "decision_date",
            "days_ex_to_decision",
            "fiscal_year",
        ],
    )
    result = events.join(matched.set_index("event_idx"), how="left")
    unmatched_decisions = decisions.drop(index=list(used_d))
    return result, unmatched_decisions


def reconcile(
    tickers: list[str] = KR_STOCK_TICKERS,
    fiscal_years: range = range(2018, 2026),
    since: str = EVENTS_SINCE,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """반환: (건별 매칭표, 사업연도별 금액 대조표)."""
    api_key = _require_key()
    corp_map = fetch_corp_code_map(api_key)
    yahoo = pd.read_parquet(PROCESSED_DIR / "dividends.parquet")
    yahoo["ex_date"] = pd.to_datetime(yahoo["ex_date"])
    since_ts = pd.Timestamp(since)

    event_rows, fy_rows = [], []
    for ticker in tickers:
        corp_code = corp_map.loc[corp_map.stock_code == ticker, "corp_code"].iloc[0]
        events = yahoo[(yahoo.ticker == ticker) & (yahoo.ex_date >= since_ts)][
            ["ex_date", "amount"]
        ]
        events = events.sort_values("ex_date").reset_index(drop=True)
        decisions = fetch_dividend_decisions(corp_code, api_key=api_key)
        matched, orphan_decisions = match_events(events, decisions)
        matched.insert(0, "ticker", ticker)
        matched["status"] = matched["rcept_no"].map(
            lambda x: "matched" if pd.notna(x) else "yahoo_only"
        )
        event_rows.append(matched)
        # since 이전 배당락을 결정한 공시(예: 2017년 3분기분)는 대상이 아니므로 뺀다.
        orphan_cutoff = since_ts + pd.DateOffset(days=MATCH_MAX_DAYS)
        orphan_decisions = orphan_decisions[
            orphan_decisions["decision_date"].ge(orphan_cutoff)
        ]
        for _, dc in orphan_decisions.iterrows():
            event_rows.append(
                pd.DataFrame(
                    [
                        {
                            "ticker": ticker,
                            "ex_date": pd.NaT,
                            "amount": None,
                            "rcept_no": dc["rcept_no"],
                            "decision_date": dc["decision_date"],
                            "days_ex_to_decision": None,
                            "fiscal_year": fiscal_year_of_decision(dc["decision_date"]),
                            "status": "dart_only",
                        }
                    ]
                )
            )

        for fy in fiscal_years:
            yahoo_sum = float(matched.loc[matched.fiscal_year == fy, "amount"].sum())
            n_events = int((matched.fiscal_year == fy).sum())
            dart = fetch_dividend_disclosure(corp_code, fy, api_key)
            dart_val = dart["per_share_cash_dividend"] if dart else None
            ok = dart_val is not None and abs(yahoo_sum - dart_val) < 0.5
            fy_rows.append(
                {
                    "ticker": ticker,
                    "fiscal_year": fy,
                    "n_events": n_events,
                    "yahoo_sum": round(yahoo_sum, 2),
                    "dart_per_share": dart_val,
                    "match": ok,
                }
            )
    events_df = pd.concat(event_rows, ignore_index=True)
    return events_df, pd.DataFrame(fy_rows)


if __name__ == "__main__":
    events_df, fy_df = reconcile()
    out_dir = PROCESSED_DIR
    events_df.to_csv(out_dir / "dart_dividend_events.csv", index=False)
    fy_df.to_csv(out_dir / "dart_dividend_reconciliation.csv", index=False)

    print(fy_df.to_string(index=False))
    print()
    print(events_df["status"].value_counts().to_string())
    problems = events_df[events_df.status != "matched"]
    if len(problems):
        print("\n짝이 없는 건:")
        print(problems.to_string(index=False))
    print(f"\n사업연도 금액 일치: {int(fy_df.match.sum())}/{len(fy_df)}")
    print(
        f"-> {out_dir / 'dart_dividend_events.csv'}, {out_dir / 'dart_dividend_reconciliation.csv'}"
    )
