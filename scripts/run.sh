#!/bin/bash
# koe-input.app から呼ばれる起動スクリプト。
# 終了コード 42（= アップデートや設定変更のための再起動）のときは、もう一度起動する。
# 予期せず落ちた場合も、短時間に何度も落ちない限り自動で起動し直す。
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export PYTHONUNBUFFERED=1
DIR="$HOME/koe-input"
cd "$DIR" || exit 1
mkdir -p data
LOG="$DIR/data/koe.log"
crashes=0
first_crash=0

while true; do
  # ログが 5MB を超えたら古い方に回す
  if [ -f "$LOG" ] && [ "$(stat -f%z "$LOG" 2>/dev/null || echo 0)" -gt 5000000 ]; then
    mv -f "$LOG" "$LOG.old"
  fi
  echo "---- $(date '+%Y-%m-%d %H:%M:%S') 起動 ----" >> "$LOG"
  uv run python -m koe >> "$LOG" 2>&1
  code=$?
  echo "---- $(date '+%Y-%m-%d %H:%M:%S') 終了（コード ${code}）----" >> "$LOG"
  if [ "$code" -eq 42 ]; then
    continue
  fi
  # 0 = メニューから終了 / 143 = インストーラなどによる停止
  if [ "$code" -eq 0 ] || [ "$code" -eq 143 ]; then
    break
  fi
  # それ以外 = 異常終了。2分以内に3回落ちたら諦めて知らせる
  now=$(date +%s)
  if [ $((now - first_crash)) -gt 120 ]; then
    first_crash=$now
    crashes=0
  fi
  crashes=$((crashes + 1))
  if [ "$crashes" -ge 3 ]; then
    osascript -e 'display notification "停止しました。~/koe-input/data/koe.log を確認してください" with title "koe-input"' >/dev/null 2>&1
    break
  fi
  sleep 1
done
