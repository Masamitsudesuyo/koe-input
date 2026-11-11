#!/bin/bash
# koe-input.app から呼ばれる起動スクリプト。
# 終了コード 42（= アップデートや設定変更のための再起動）のときは、もう一度起動する。
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export PYTHONUNBUFFERED=1
DIR="$HOME/koe-input"
cd "$DIR" || exit 1
mkdir -p data
LOG="$DIR/data/koe.log"

while true; do
  # ログが 5MB を超えたら古い方に回す
  if [ -f "$LOG" ] && [ "$(stat -f%z "$LOG" 2>/dev/null || echo 0)" -gt 5000000 ]; then
    mv -f "$LOG" "$LOG.old"
  fi
  echo "---- $(date '+%Y-%m-%d %H:%M:%S') 起動 ----" >> "$LOG"
  uv run python -m koe >> "$LOG" 2>&1
  code=$?
  if [ "$code" -eq 42 ]; then
    continue
  fi
  # 0 = メニューから終了 / 143 = インストーラによる停止。それ以外は異常終了
  if [ "$code" -ne 0 ] && [ "$code" -ne 143 ]; then
    osascript -e 'display notification "停止しました。~/koe-input/data/koe.log を確認してください" with title "koe-input"' >/dev/null 2>&1
  fi
  break
done
