#!/usr/bin/env bash
# 매 거래일 장 마감 뒤 cron이 실행한다: 증분 갱신 -> 명세 8장 검증. 결과는 logs/update.log에 남는다.
# scripts/README.md의 "로직 없는 얇은 python 진입점" 틀과는 다른, A의 운영 서버(cron·Discord
# 알림) 전용 bash 스크립트다 — src/roboadvisor/data/collectors 등으로 재정리할 때 같이 논의.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$ROOT/logs/update.log"
LOGIN_LOG="$ROOT/logs/login_warnings.log"  # 로그인/만료 줄은 버리지 않고 여기로 (반복되면 알아챌 수 있게)
mkdir -p "$ROOT/logs"
cd "$ROOT" || exit 1

{
  echo "===== $(TZ=Asia/Seoul date '+%Y-%m-%d %H:%M:%S KST') ====="
  set -a; . "$ROOT/.env"; set +a
  export PYTHONPATH="$ROOT/src"
  "$ROOT/.venv/bin/python" -W ignore -m roboadvisor.data.update
  update_rc=$?
  validate_rc=0
  if [ "$update_rc" -eq 0 ]; then
    "$ROOT/.venv/bin/python" -W ignore -m roboadvisor.data.validate
    validate_rc=$?
  fi
  if [ "$update_rc" -eq 0 ] && [ "$validate_rc" -eq 0 ]; then
    echo "RESULT: OK"
  else
    echo "RESULT: FAIL (update=$update_rc validate=$validate_rc)"
  fi
} 2>&1 | tee >(grep "로그인\|만료" >> "$LOGIN_LOG") | grep -v "로그인\|만료" >> "$LOG"

set -a; . "$ROOT/.env"; set +a
"$ROOT/.venv/bin/python" "$ROOT/scripts/notify_discord.py" "$LOG" >> "$LOG" 2>&1

grep "^RESULT:" "$LOG" | tail -1 | grep -q "RESULT: OK"
