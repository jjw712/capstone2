#!/usr/bin/env bash
# 자동 수집·디스코드 알림 관리.
#   scripts/ctl.sh                 메뉴
#   scripts/ctl.sh status          현재 상태
#   scripts/ctl.sh recent [N]      최근 N회 실행 기록 (기본 3)
#   scripts/ctl.sh auto on|off     자동 수집(cron) 켜기/끄기
#   scripts/ctl.sh discord on|off  디스코드 알림 켜기/끄기
# 리눅스(GNU date/sed) 전용. 웹후크 주소는 어디에도 출력하지 않는다.
umask 077
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
JOB="$ROOT/scripts/daily_update.sh"
ENVF="$ROOT/.env"
LOG="$ROOT/logs/update.log"
OFFMARK="#OFF# "

# ---------- 자동 수집 (cron) ----------
cron_read() { crontab -l 2>/dev/null; }

# ctl.sh를 어느 경로(실제 경로든 심볼릭 링크든)로 실행했는지와 무관하게 같은 잡을
# 찾아야 한다 — 전에는 $JOB 문자열을 그대로 부분일치시켜서, 프로젝트 폴더가
# 바뀌면(예: a2b_vdi_2026-10-10 -> capdDATA) 기존 crontab 줄과 안 맞아 새 줄을
# 또 추가하고 옛 줄은 죽은 채로 남았다(실제로 그렇게 생긴 중복을 2026-10-12에
# 발견해 지움). realpath로 정규화해서 비교하면 어느 경로로 불러도 같은 잡으로 본다.
JOB_REAL="$(readlink -f "$JOB" 2>/dev/null || echo "$JOB")"

line_is_job() {  # $1 = crontab 원문 한 줄 (OFFMARK 접두어 포함 가능)
  local line="${1#"$OFFMARK"}" cmd
  [ -z "$line" ] && return 1
  cmd="$(awk '{print $NF}' <<<"$line")"
  [ -z "$cmd" ] && return 1
  [ "$(readlink -f "$cmd" 2>/dev/null || echo "$cmd")" = "$JOB_REAL" ]
}

cron_state() {  # on | off | none
  local line state=none
  while IFS= read -r line; do
    if line_is_job "$line"; then
      if [[ "$line" == "$OFFMARK"* ]]; then state=off; else state=on; break; fi
    fi
  done < <(cron_read)
  echo "$state"
}

cron_active_line() {
  local line
  while IFS= read -r line; do
    if line_is_job "$line" && [[ "$line" != "$OFFMARK"* ]]; then echo "$line"; return; fi
  done < <(cron_read)
}

cron_set() {  # $1 = on | off
  local want=$1 line out="" found=0 h
  while IFS= read -r line; do
    if line_is_job "$line"; then
      found=1
      if [[ "$line" == "$OFFMARK"* ]]; then
        [ "$want" = on ] && line="${line#"$OFFMARK"}"
      else
        [ "$want" = off ] && line="$OFFMARK$line"
      fi
    fi
    out+="$line"$'\n'
  done < <(cron_read)
  if [ "$found" = 0 ]; then
    [ "$want" = off ] && return 0
    [ -x "$JOB" ] || chmod +x "$JOB"
    h=$(date -d 'TZ="Asia/Seoul" 18:30' +%H 2>/dev/null || echo 18)
    out+="# A->B 데이터 증분 갱신: 평일 18:30 KST"$'\n'"30 $h * * 1-5 $JOB"$'\n'
  fi
  printf '%s' "$out" | crontab -
}

next_run() {  # $1=시 $2=분 (cron과 같은 현지 시각, 평일만)
  local i t now dow
  now=$(date +%s)
  for i in 0 1 2 3 4 5 6 7; do
    t=$(date -d "today +$i days $1:$2" +%s 2>/dev/null) || return
    dow=$(date -d "@$t" +%u)
    if [ "$t" -gt "$now" ] && [ "$dow" -le 5 ]; then date -d "@$t" '+%m/%d(%a) %H:%M %Z'; return; fi
  done
}

# ---------- 디스코드 알림 ----------
discord_state() {  # on | off | unset
  if grep -q '^[[:space:]]*DISCORD_WEBHOOK_URL=.\+' "$ENVF" 2>/dev/null; then echo on
  elif grep -q '^#[[:space:]]*DISCORD_WEBHOOK_URL=.\+' "$ENVF" 2>/dev/null; then echo off
  else echo unset; fi
}

discord_set() {  # $1 = on | off
  if [ "$1" = off ]; then
    sed -i.bak 's/^\([[:space:]]*\)DISCORD_WEBHOOK_URL=/\1#DISCORD_WEBHOOK_URL=/' "$ENVF"
  else
    sed -i.bak 's/^\([[:space:]]*\)#DISCORD_WEBHOOK_URL=/\1DISCORD_WEBHOOK_URL=/' "$ENVF"
  fi
  rm -f "$ENVF.bak"
}

# ---------- 보기 ----------
status() {
  local cs ds line m h last
  cs=$(cron_state); ds=$(discord_state)
  echo "=== 현재 상태: $(hostname) · $(date '+%Y-%m-%d %H:%M %Z') ==="
  case $cs in
    on)   line=$(cron_active_line); read -r m h _ <<<"$line"
          printf '자동 수집    : 켜짐   (평일 %02d:%02d %s) · 다음 실행 %s\n' "$h" "$m" "$(date +%Z)" "$(next_run "$h" "$m")" ;;
    off)  echo "자동 수집    : 꺼짐" ;;
    none) echo "자동 수집    : 예약 없음 (3번으로 켜면 새로 등록)" ;;
  esac
  case $ds in
    on)    [ "$cs" = on ] && echo "디스코드 알림: 켜짐" || echo "디스코드 알림: 켜짐   (자동 수집이 꺼져 있어 지금은 아무것도 안 감)" ;;
    off)   echo "디스코드 알림: 꺼짐   (주소는 .env에 남아 있음)" ;;
    unset) echo "디스코드 알림: 주소 없음 (.env에 DISCORD_WEBHOOK_URL 필요)" ;;
  esac
  if [ -x "$ROOT/.venv/bin/python" ] && [ -f "$ROOT/data/processed/returns.parquet" ]; then
    last=$("$ROOT/.venv/bin/python" -W ignore -c "
import pandas as pd
d = pd.read_parquet('$ROOT/data/processed/returns.parquet', columns=['date'])['date']
print(d.max().date(), f'({d.nunique()}거래일)')" 2>/dev/null)
    echo "데이터       : 마지막 거래일 ${last:-읽기 실패}"
  fi
  if [ -f "$LOG" ]; then
    echo "마지막 실행  : $(recent 1 | tail -1)"
  else
    echo "마지막 실행  : 기록 없음"
  fi
  echo "--- 점검"
  local svc; svc=$(systemctl is-active cron 2>/dev/null || systemctl is-active crond 2>/dev/null)
  [ "$svc" = active ] && echo "cron 서비스  : 동작 중" || echo "cron 서비스  : ⚠ ${svc:-확인 불가} (자동 수집이 실행되지 않을 수 있음)"
  local missing=""
  for k in KRX_ID KRX_PW OPENDART_API_KEY; do
    grep -q "^[[:space:]]*$k=.\+" "$ENVF" 2>/dev/null || missing+="$k "
  done
  [ -z "$missing" ] && echo ".env 키      : KRX_ID, KRX_PW, OPENDART_API_KEY 있음" || echo ".env 키      : ⚠ 없음 -> $missing"
  local perm; perm=$(stat -c %a "$ENVF" 2>/dev/null)
  [ "$perm" = 600 ] || echo ".env 권한    : ⚠ ${perm:-파일 없음} (600 권장: chmod 600 .env)"
}

recent() {  # $1 = 최근 몇 회 (기본 3)
  local n=${1:-3}
  [ -f "$LOG" ] || { echo "아직 실행 기록이 없습니다 ($LOG)"; return; }
  awk -v n="$n" '
    function flush() {
      if (h == "") return
      c++; H[c]=h; R[c]=res; U[c]=upd; N[c]=nt; F[c]=fl
    }
    /^===== / { flush(); h=$0; gsub(/^===== | =====$/, "", h); res=""; upd=""; nt=""; fl=""; next }
    /^RESULT:/ { res=$0 }
    /^\[update\]/ { if (upd == "" && $0 !~ /경고/) upd=$0 }
    /-> FAIL|Traceback|Error/ { if (fl == "") fl=$0 }
    /^\[notify\]/ { nt=$0 }
    END {
      flush()
      s = c - n + 1; if (s < 1) s = 1
      for (i = s; i <= c; i++) {
        ok = (R[i] ~ /^RESULT: OK/)
        u = U[i]; sub(/^\[update\] /, "", u)
        if (u ~ /이미 최신/) sm = "새 데이터 없음"
        else if (u ~ /일 추가/) { sub(/ \(KOSPI.*/, "", u); sm = u }
        else sm = (u != "" ? u : "(요약 없음)")
        if (!ok && F[i] != "") sm = sm " / " substr(F[i], 1, 60)
        nt = N[i]
        if (nt ~ /HTTP 2/) a = "알림 보냄"
        else if (nt ~ /조용히/) a = "알림 없음(새 데이터 없음)"
        else if (nt ~ /생략/) a = "알림 꺼짐"
        else if (nt ~ /실패/) a = "⚠ 알림 전송 실패"
        else a = "알림 기록 없음"
        printf "%s  %s  %s  | %s\n", substr(H[i], 1, 16), (ok ? "✅ OK  " : "❌ FAIL"), sm, a
      }
    }' "$LOG"
}

# ---------- 바꾸기 ----------
label() { case $1 in on) echo 켜짐;; off) echo 꺼짐;; none) echo "예약 없음";; unset) echo "주소 없음";; esac; }

toggle() {  # $1 = auto | discord
  local cur a
  if [ "$1" = auto ]; then cur=$(cron_state); else cur=$(discord_state); fi
  echo "현재: $(label "$cur")"
  [ "$cur" = unset ] && { echo ".env에 DISCORD_WEBHOOK_URL=... 줄을 먼저 넣어야 합니다."; return; }
  read -r -p "1) 켜기  2) 끄기  (Enter: 취소) > " a
  case $a in
    1) if [ "$1" = auto ]; then cron_set on; else discord_set on; fi ;;
    2) if [ "$1" = auto ]; then cron_set off; else discord_set off; fi ;;
    *) echo "취소"; return ;;
  esac
  if [ "$1" = auto ]; then echo "변경 후: $(label "$(cron_state)")"; else echo "변경 후: $(label "$(discord_state)")"; fi
}

menu() {
  local c n
  while true; do
    echo
    echo "1) 현재 상태   2) 최근 실행 기록   3) 자동 수집 켜기/끄기   4) 디스코드 알림 켜기/끄기   q) 종료"
    read -r -p "선택> " c || break
    case $c in
      1) status ;;
      2) read -r -p "최근 몇 회? [3] " n; recent "${n:-3}" ;;
      3) toggle auto ;;
      4) toggle discord ;;
      q|Q) break ;;
      *) echo "1~4 또는 q를 입력하세요." ;;
    esac
  done
}

case "${1:-menu}" in
  menu)    menu ;;
  status)  status ;;
  recent)  recent "${2:-3}" ;;
  auto)    case "${2:-}" in on|off) cron_set "$2"; echo "자동 수집: $(label "$(cron_state)")" ;; *) echo "사용: ctl.sh auto on|off"; exit 2 ;; esac ;;
  discord) case "${2:-}" in on|off) discord_set "$2"; echo "디스코드 알림: $(label "$(discord_state)")" ;; *) echo "사용: ctl.sh discord on|off"; exit 2 ;; esac ;;
  *)       sed -n '2,8p' "$0"; exit 2 ;;
esac

