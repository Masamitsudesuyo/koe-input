"""画面右上のメニューバーに常駐するアイコンとメニュー（Mac 専用）。"""
import os
import subprocess
import threading
import time

import rumps

from . import macos, updater
from .config import CONFIG_PATH, DICT_PATH

ICONS = {"idle": "🎙", "rec": "🔴", "busy": "⏳", "error": "⚠️"}
LABELS = {"idle": "待機中", "rec": "録音中…", "busy": "変換中…", "error": "エラー（履歴を確認）"}


class MenuBar(rumps.App):
    def __init__(self, app, hist_url: str):
        super().__init__("koe-input", title=ICONS["idle"], quit_button=None)
        self.app = app
        self.hist_url = hist_url
        self.status_item = rumps.MenuItem("状態: 待機中")
        ver = updater.local_version()[:7] or "開発版"
        self.version_item = rumps.MenuItem(f"バージョン: {ver}")
        self.menu = [
            self.status_item,
            None,
            rumps.MenuItem("直前の結果をコピー", callback=self.copy_last),
            rumps.MenuItem("履歴を開く", callback=self.open_history),
            rumps.MenuItem("辞書を編集", callback=self.open_dict),
            rumps.MenuItem("設定を編集", callback=self.open_config),
            None,
            rumps.MenuItem("アップデートを確認", callback=self.check_update),
            rumps.MenuItem("再起動（設定の反映）", callback=self.restart),
            self.version_item,
            None,
            rumps.MenuItem("終了", callback=self.quit),
        ]
        self._shown = None
        self.overlay = None
        try:
            from .overlay import Overlay
            self.overlay = Overlay()
        except Exception as e:
            print(f"（画面下の表示を作れませんでした: {e}）", flush=True)
        # 0.1秒ごとに状態を画面へ反映（画面の更新はこのスレッドでしかできないため）
        self.timer = rumps.Timer(self.tick, 0.1)
        self.timer.start()

    def tick(self, _):
        st = self.app.status
        if st != self._shown:
            self.title = ICONS.get(st, ICONS["idle"])
            self.status_item.title = f"状態: {LABELS.get(st, st)}"
            self._shown = st
        self.update_overlay(st)
        if self.app.restart_requested and self.app.is_idle():
            os._exit(42)  # 42 = 「再起動して」の合図。scripts/run.sh が受け取って起動し直す

    def update_overlay(self, st):
        if not self.overlay:
            return
        try:
            now = time.monotonic()
            if st == "rec":
                sec = int(now - self.app.rec_started)
                self.overlay.show(f"🔴 録音中  {sec // 60}:{sec % 60:02d}")
            elif st == "busy":
                self.overlay.show("⏳ 変換中…")
            elif now < self.app.flash_until:
                self.overlay.show(self.app.flash_text)
            else:
                self.overlay.hide()
        except Exception as e:
            print(f"（画面下の表示でエラー: {e}）", flush=True)
            self.overlay = None

    def copy_last(self, _):
        if self.app.last_text:
            macos.set_clipboard(self.app.last_text)

    def open_history(self, _):
        subprocess.Popen(["open", self.hist_url])

    def open_dict(self, _):
        subprocess.Popen(["open", "-e", str(DICT_PATH)])

    def open_config(self, _):
        subprocess.Popen(["open", "-e", str(CONFIG_PATH)])
        macos.notify("koe-input", "設定を保存したら、メニューの「再起動（設定の反映）」を押してください")

    def check_update(self, _):
        def run():
            try:
                updated, msg = updater.check_and_update()
            except Exception as e:
                updated, msg = False, f"確認できませんでした: {e}"
            macos.notify("koe-input アップデート", msg)
            if updated:
                self.app.restart_requested = True
        threading.Thread(target=run, daemon=True).start()

    def restart(self, _):
        self.app.restart_requested = True

    def quit(self, _):
        os._exit(0)


def run_menubar(app, hist_url: str):
    try:
        # Dock にアイコンを出さない（メニューバーだけに出す）
        from AppKit import NSApplication
        NSApplication.sharedApplication().setActivationPolicy_(1)
    except Exception:
        pass
    MenuBar(app, hist_url).run()
