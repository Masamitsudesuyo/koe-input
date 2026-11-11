# セットアップ手順（アプリ版）

## インストール（初回・1回だけ）

【ターミナルで実行】

```
curl -fsSL https://raw.githubusercontent.com/Masamitsudesuyo/koe-input/main/install.sh | bash
```

このコマンドで次のことが自動で行われます。

1. 最新のプログラムを `~/koe-input` にダウンロード（`config.toml`・`dictionary.txt`・履歴は残る）
2. `/Applications/koe-input.app` を作成
3. Mac にログインしたとき自動で起動するよう登録
4. アプリを起動（画面右上のメニューバーに 🎙 が出る）

## Mac の許可（初回のみ）

アプリ版では、許可の対象が「ターミナル」ではなく「koe-input」になります。

システム設定 → プライバシーとセキュリティ で、次の3つに「koe-input」をオンにする。

- 入力監視
- アクセシビリティ
- マイク（初回録音時に出る確認で「許可」を押してもよい）

許可した後は、メニューバーの 🎙 →「再起動（設定の反映）」を押す。

## 使い方

- Option+Command を押して離す → 話す → もう一度 Option+Command で入力
- Esc で取り消し
- 🎙 = 待機中 / 🔴 = 録音中 / ⏳ = 変換中 / ⚠️ = エラー
- メニューバーの 🎙 から、履歴・辞書・設定を開ける

## アップデート

GitHub（Masamitsudesuyo/koe-input）が更新されると、アプリが6時間以内に自動で取り込みます。
すぐに取り込みたいときは、🎙 →「アップデートを確認」を押します。

## うまく動かないとき

動作ログは `~/koe-input/data/koe.log` にあります。

【ターミナルで実行】最後の30行を表示する:

```
tail -n 30 ~/koe-input/data/koe.log
```
