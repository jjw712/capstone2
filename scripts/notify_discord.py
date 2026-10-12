"""갱신 결과를 Discord 웹후크로 알린다.

    python scripts/notify_discord.py <로그파일> [--weekly | --daily | --test]

DISCORD_WEBHOOK_URL 환경변수가 없으면 아무것도 보내지 않고 종료한다(갱신 자체는 영향 없음).
로그의 마지막 실행 구간을 읽어 다음처럼 보낸다.
  - 실패                         -> 항상: 실패 알림 + 로그 끝부분
  - 평일(월~목), 새 거래일 있음  -> 그날 수집한 데이터 요약(글만, 파일 없음)
  - 평일(월~목), 새 데이터 없음  -> 조용히 종료 (휴장일)
  - 금요일(KST)                  -> 그날 요약 + 이번 주 일별 현황 + 최신 데이터 zip. 휴장이어도 보낸다
--weekly / --daily 로 요일 판정을 강제할 수 있다(시험용).
"""

from __future__ import annotations

import io
import json
import os
import re
import sys
import uuid
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib import request

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
ATTACH = [
    "returns.parquet",
    "features.parquet",
    "benchmark.parquet",
    "dividends.parquet",
]
DOCS = [
    ROOT / "docs" / "interfaces.md",
    ROOT / "src" / "roboadvisor" / "data" / "preprocessing.py",
    ROOT / "configs" / "assets.yaml",
    ROOT / "configs" / "data.yaml",
    ROOT / "configs" / "experiments.yaml",
]


def last_run(log: Path) -> list[str]:
    lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    starts = [i for i, l in enumerate(lines) if l.startswith("===== ")]
    return lines[starts[-1] :] if starts else lines


def build_zip(last_date: str) -> bytes:
    buf = io.BytesIO()
    root = f"a2b_data_{last_date}"
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name in ATTACH:
            z.write(PROCESSED / name, f"{root}/data/processed/{name}")
        for p in DOCS:
            z.write(p, f"{root}/{p.relative_to(ROOT)}")
        z.writestr(
            f"{root}/MANIFEST.txt",
            f"A->B 데이터 전달물, 마지막 거래일 {last_date}. 명세: docs/interfaces.md\n"
            "정규화: src/roboadvisor/data/preprocessing.py::fit_normalization_stats\n"
            "(configs/assets.yaml 필요)\n",
        )
    return buf.getvalue()


def post(url: str, text: str, attachment: tuple[str, bytes] | None = None) -> int:
    payload = json.dumps({"content": text[:1900]}).encode()
    if attachment is None:
        req = request.Request(
            url,
            payload,
            {"Content-Type": "application/json", "User-Agent": "a2b-notify/1.0"},
        )
    else:
        b = uuid.uuid4().hex
        name, data = attachment
        disposition = (
            f"\r\n--{b}\r\nContent-Disposition: form-data; "
            f'name="files[0]"; filename="{name}"\r\n'
        )
        body = (
            (
                f'--{b}\r\nContent-Disposition: form-data; name="payload_json"\r\n'
                f"Content-Type: application/json\r\n\r\n"
            ).encode()
            + payload
            + (disposition + "Content-Type: application/zip\r\n\r\n").encode()
            + data
            + f"\r\n--{b}--\r\n".encode()
        )
        req = request.Request(
            url,
            body,
            {
                "Content-Type": f"multipart/form-data; boundary={b}",
                "User-Agent": "a2b-notify/1.0",
            },
        )
    with request.urlopen(req, timeout=60) as r:
        return r.status


def week_digest(log: Path, today: date) -> list[str]:
    """최근 7일(오늘 포함) 실행 기록을 날짜별 한 줄로."""
    text = log.read_text(encoding="utf-8", errors="replace")
    days: dict[date, str] = {}
    for chunk in text.split("===== ")[1:]:
        m = re.match(r"(\d{4})-(\d{2})-(\d{2}) ", chunk)
        if not m:
            continue
        d = date(int(m[1]), int(m[2]), int(m[3]))
        if not (today - timedelta(days=6) <= d <= today):
            continue
        res = next(
            (
                line
                for line in reversed(chunk.splitlines())
                if line.startswith("RESULT:")
            ),
            "RESULT: 없음",
        )
        added = next(
            (
                line
                for line in chunk.splitlines()
                if line.startswith("[update]") and "일 추가" in line
            ),
            None,
        )
        if not res.startswith("RESULT: OK"):
            days[d] = "❌ 실패"
        elif added:
            days[d] = "✅ " + re.search(r"(\d+일 추가: [\d-]+~[\d-]+)", added)[1]
        else:
            days[d] = "· 새 데이터 없음 (휴장)"
    wd = "월화수목금토일"
    return [
        f"{d.month}/{d.day}({wd[d.weekday()]}) {v}" for d, v in sorted(days.items())
    ]


def main() -> int:
    url = os.getenv("DISCORD_WEBHOOK_URL")
    prefix = os.getenv("NOTIFY_PREFIX", "")  # 수동 테스트 때 "[테스트] "처럼 표시용
    if not url:
        print("[notify] DISCORD_WEBHOOK_URL 없음 — 알림 생략")
        return 0
    if "--test" in sys.argv:
        print(
            "[notify] test HTTP",
            post(
                url,
                "🔔 A->B 데이터 갱신 알림 연결 테스트 (이 메시지는 무시해도 됩니다)",
            ),
        )
        return 0

    log = Path(sys.argv[1])
    run = last_run(log)
    header = run[0].strip("= ").strip() if run else ""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", header)
    today = (
        date(*map(int, m.groups()))
        if m
        else datetime.now(ZoneInfo("Asia/Seoul")).date()
    )
    weekly = "--weekly" in sys.argv or (
        "--daily" not in sys.argv and today.weekday() == 4
    )
    result = next(
        (line for line in reversed(run) if line.startswith("RESULT:")),
        "RESULT: 없음(스크립트가 중간에 죽음)",
    )

    if not result.startswith("RESULT: OK"):
        # 고정된 마지막 N줄만 보내면 실패 원인이 많을 때(예: ETF 6종이 전부 FAIL)
        # 뒤쪽 FAIL들에 가려 앞쪽 FAIL들이 잘려 나간다(2026-10-12 실측: 6개 중
        # 1개만 알림에 보였음). 문제 줄(FAIL/Traceback/Error)만 모아 보낸다 —
        # 그런 줄이 하나도 없으면(스크립트가 중간에 죽은 경우 등) 기존처럼 끝부분을 보여준다.
        problem_lines = [
            line
            for line in run
            if ("-> FAIL" in line) or ("Traceback" in line) or ("Error" in line)
        ]
        tail = "\n".join(problem_lines) if problem_lines else "\n".join(run[-12:])
        print(
            "[notify] HTTP",
            post(
                url,
                f"{prefix}❌ **데이터 갱신 실패** ({header})\n{result}\n```\n{tail}\n```",
            ),
        )
        return 0

    detail = [
        line.replace("[update] ", "")
        for line in run
        if line.startswith("[update]") and "경고" not in line
    ]
    added = next(
        (line for line in run if line.startswith("[update]") and "일 추가" in line),
        None,
    )
    n_checks = sum(1 for line in run if line.endswith("-> OK"))
    if added is None and not weekly:
        print("[notify] 새 거래일 없음 — 조용히 종료")
        return 0

    if added:
        text = (
            f"{prefix}✅ **데이터 갱신 완료** ({header})\n```\n"
            + "\n".join(detail)
            + f"\n검증 {n_checks}개 항목 통과\n```"
        )
    else:
        text = f"{prefix}· **{header}** 새 거래일 없음 (휴장일)"
    if not weekly:
        print("[notify] HTTP", post(url, text))
        return 0

    last_date = sorted(pd_dates(PROCESSED / "returns.parquet"))[-1]
    text += (
        "\n**이번 주 현황**\n"
        + "\n".join(week_digest(log, today))
        + f"\n최신 데이터({last_date}까지) 첨부"
    )
    print(
        "[notify] HTTP",
        post(url, text, (f"a2b_data_{last_date}.zip", build_zip(last_date))),
    )
    return 0


def pd_dates(path: Path) -> list[str]:
    import pandas as pd

    return (
        pd.read_parquet(path, columns=["date"])["date"]
        .dt.strftime("%Y-%m-%d")
        .unique()
        .tolist()
    )


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # 알림 실패가 갱신 결과에 영향을 주면 안 됨
        print(f"[notify] 알림 전송 실패: {exc}", file=sys.stderr)
        sys.exit(0)
