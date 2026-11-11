# koe-input（自作の音声入力ツール）

Typeless と同じ流れを自分の Mac で動かすためのツールです。

## 仕組み

Typeless もこのツールも、次の5段階で動いています。

1. **ホットキー検知**: Option+Command が押されたことを検知する
2. **録音**: マイクの音を記録する
3. **音声認識（STT = Speech To Text、声を文字にする処理）**: 録音をクラウドの AI に送り、文字にしてもらう
4. **整形（LLM = 大規模言語モデル、ChatGPT のような文章 AI）**: 文字起こしを AI に送り、フィラー削除・言い直しの反映・きれいな日本語への変換をしてもらう
5. **貼り付け**: 結果をクリップボードに入れ、Command+V を自動で押して、いまカーソルがある場所に入力する

あわせて、結果は Mac 内のデータベース（`data/history.db`）に保存され、履歴ページから後でコピーできます。

| Typeless の機能 | このツールでの実現方法 |
|---|---|
| 1. 声で入力 | 音声認識 API（Groq: whisper-large-v3-turbo / OpenAI: gpt-4o-mini-transcribe） |
| 2. フィラー削除 | 整形 AI への指示文（`koe/engine.py` の `SYSTEM_PROMPT`） |
| 3. 「xxじゃなかったyy」 | 同上。訂正前の語を消すよう指示 |
| 4. きれいな日本語に | 同上 |
| 5. 辞書 | `dictionary.txt`。音声認識と整形 AI にヒントとして渡し、最後に置換もする |
| 6. Option+Command で起動 | `koe/hotkey.py` |
| 7. 過去の結果を残す | 履歴ページ http://127.0.0.1:8765 |

## 使い方

- Option+Command を押して離す → 話す → もう一度 Option+Command で入力。Esc で取り消し
- 設定で `mode = "hold"` にすると、押している間だけ録音する動作になる
- 画面右上のメニューバーの 🎙 から、履歴・辞書・設定を開ける（🔴 = 録音中、⏳ = 変換中）

## アプリ化と自動アップデート

- `install.sh` が `/Applications/koe-input.app` を作り、ログイン時に自動で起動するよう登録する
- アプリは起動時と6時間ごとに GitHub を確認し、新しい版があれば取り込んで、使っていないときに自動で再起動する
- `config.toml`・`dictionary.txt`・`data/`（履歴）はアップデートで上書きされない
- 動作ログ: `~/koe-input/data/koe.log`

## 費用の目安

| サービス | 費用 |
|---|---|
| Groq | 無料枠内で使える（1日 約1,000回までの上限あり） |
| OpenAI | 音声 1分 $0.003 ＋ 整形 1回 約$0.0005。1日10分話して月 約$1.5（約230円）の計算 |

※ 料金は 2026年11月時点の公式ページの記載に基づく計算です。

## ファイル構成

```
koe-input/
├── install.sh           インストーラ（アプリ作成・ログイン時起動の登録）
├── scripts/run.sh       アプリから呼ばれる起動スクリプト
├── config.example.toml  設定のひな形（config.toml が無ければ自動で作られる）
├── dictionary.example.txt 辞書のひな形（dictionary.txt が無ければ自動で作られる）
├── koe/                 プログラム本体
│   ├── __main__.py      全体の流れ
│   ├── hotkey.py        ホットキー判定
│   ├── recorder.py      録音
│   ├── engine.py        音声認識・整形（AIへの指示文はここ）
│   ├── dictionary.py    辞書
│   ├── history.py       履歴の保存と履歴ページ
│   └── macos.py         貼り付け・効果音・通知
├── data/history.db      履歴（自動で作られる）
└── tests/               動作確認用テスト
```

セットアップ手順は SETUP.md を見てください。
