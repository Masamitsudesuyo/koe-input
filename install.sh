#!/bin/bash
# ===== koe-input インストーラ =====
# 何度実行しても大丈夫です（設定・辞書・履歴は消えません）。
set -euo pipefail

REPO="Masamitsudesuyo/koe-input"
DIR="$HOME/koe-input"
APP_NAME="koe-input"
BUNDLE_ID="com.koe-input.app"

echo ""
echo "== koe-input をインストールします =="

# --- 1. uv（Python と部品を準備する道具）---
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  echo "[1/6] uv をインストールします"
  curl -LsSf https://astral.sh/uv/install.sh | sh
else
  echo "[1/6] uv はインストール済みです"
fi

# --- 2. 動いている koe-input を止める ---
echo "[2/6] 動いている koe-input を止めます"
pkill -f "python -m koe" 2>/dev/null || true
sleep 1

# --- 3. 最新のプログラムをダウンロード ---
echo "[3/6] 最新版をダウンロードします（${REPO}）"
SHA=$(curl -fsSL -H "Accept: application/vnd.github.sha" "https://api.github.com/repos/$REPO/commits/main")
TMP=$(mktemp -d)
curl -fsSL "https://codeload.github.com/$REPO/zip/$SHA" -o "$TMP/src.zip"
unzip -q "$TMP/src.zip" -d "$TMP/src"
SRC=$(find "$TMP/src" -mindepth 1 -maxdepth 1 -type d | head -1)
mkdir -p "$DIR"
# 自分で編集するファイル（設定・辞書・履歴）は上書きしない
rsync -a \
  --exclude config.toml --exclude dictionary.txt --exclude data \
  --exclude .venv --exclude .version --exclude .repo \
  "$SRC/" "$DIR/"
echo "$SHA" > "$DIR/.version"
echo "$REPO" > "$DIR/.repo"
[ -f "$DIR/config.toml" ] || cp "$DIR/config.example.toml" "$DIR/config.toml"
[ -f "$DIR/dictionary.txt" ] || cp "$DIR/dictionary.example.txt" "$DIR/dictionary.txt"
chmod +x "$DIR/scripts/"*.sh
rm -rf "$TMP"

# --- 4. 部品の準備 ---
echo "[4/6] 必要な部品を準備します（初回は1分ほどかかります）"
(cd "$DIR" && uv sync -q)

# --- 5. アプリ本体を作る ---
APP_DIR="/Applications"
[ -w "$APP_DIR" ] || { APP_DIR="$HOME/Applications"; mkdir -p "$APP_DIR"; }
APP="$APP_DIR/$APP_NAME.app"
if [ -d "$APP" ]; then
  # 作り直すと Mac の許可（マイク等）が外れるため、既にあれば作らない
  echo "[5/6] アプリは作成済みです（${APP}）"
else
  echo "[5/6] アプリを作成します（${APP}）"
  osacompile -o "$APP" -e "do shell script \"/bin/bash '$DIR/scripts/run.sh' > /dev/null 2>&1\""
  PL="$APP/Contents/Info.plist"
  setplist() {  # 項目があれば変更、無ければ追加
    /usr/libexec/PlistBuddy -c "Set :$1 $3" "$PL" 2>/dev/null || /usr/libexec/PlistBuddy -c "Add :$1 $2 $3" "$PL"
  }
  setplist LSUIElement bool true
  setplist CFBundleIdentifier string "$BUNDLE_ID"
  setplist CFBundleName string "$APP_NAME"
  setplist NSMicrophoneUsageDescription string "音声入力のためにマイクを使います"
  codesign --force --deep -s - "$APP"
fi

# --- 6. ログイン時に自動で起動する設定 ---
echo "[6/6] ログイン時に自動で起動するよう登録します"
if osascript -e 'tell application "System Events" to get the name of every login item' 2>/dev/null | grep -q "$APP_NAME"; then
  echo "      登録済みです"
elif osascript -e "tell application \"System Events\" to make login item at end with properties {path:\"$APP\", hidden:true}" >/dev/null 2>&1; then
  echo "      登録しました"
else
  echo "      自動登録できませんでした。システム設定 → 一般 → ログイン項目 から $APP を追加してください"
fi

open "$APP"
echo ""
echo "== 完了しました =="
echo "画面右上のメニューバーに 🎙 が表示されます。"
echo "初回は Mac の許可設定が必要です（手順書を参照）。"
echo ""
