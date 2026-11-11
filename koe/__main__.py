"""koe-input 本体。`uv run python -m koe` で起動する。"""
import fcntl
import os
import subprocess
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor

from . import macos, updater
from .config import CONFIG_PATH, DATA_DIR, DICT_PATH, ConfigError, ensure_user_files, load_config
from .dictionary import Dictionary
from .engine import Engine
from .history import History, serve
from .hotkey import HotkeyStateMachine, KeyListener
from .recorder import Recorder, duration_sec, is_silent, to_wav_bytes


class App:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.b = cfg["behavior"]
        self.engine = Engine(cfg)
        self.history = History(DATA_DIR / "history.db")
        self.recorder = Recorder()
        self.worker = ThreadPoolExecutor(max_workers=1)  # 1件ずつ順番に処理する
        self.recording = False
        self.pending = 0                 # 変換待ち・変換中の件数
        self.status = "idle"             # idle / rec / busy / error（メニューバーの表示用）
        self.last_text = ""
        self.restart_requested = False
        self.lock = threading.Lock()
        tap = 1e9 if self.b["mode"] == "toggle" else self.b["tap_threshold_sec"]
        self.sm = HotkeyStateMachine(
            on_start=self.start, on_stop=self.stop, on_cancel=self.cancel, tap_threshold=tap,
        )

    def sound(self, name):
        if self.b["sounds"]:
            macos.play(name)

    def is_idle(self) -> bool:
        return not self.recording and self.pending == 0

    def _refresh_status(self):
        if self.recording:
            self.status = "rec"
        elif self.pending:
            self.status = "busy"
        elif self.status != "error":
            self.status = "idle"

    # ---- ホットキーから呼ばれる ----
    def start(self):
        with self.lock:
            try:
                self.recorder.start()
                self.recording = True
                self.status = "rec"
                self.sound("start")
                print("● 録音中…", flush=True)
            except Exception as e:
                self.status = "error"
                self.sound("error")
                macos.notify("koe-input", f"マイクを開けません: {e}")
                print(f"マイクエラー: {e}", flush=True)

    def stop(self):
        with self.lock:
            if not self.recording:
                return
            audio = self.recorder.stop()
            self.recording = False
            self.pending += 1
            self.status = "busy"
        self.sound("stop")
        self.worker.submit(self._process_wrapper, audio)

    def cancel(self):
        with self.lock:
            if self.recording:
                self.recorder.stop()
                self.recording = False
                self._refresh_status()
                self.sound("cancel")
                print("× 取り消しました", flush=True)

    def _process_wrapper(self, audio):
        try:
            ok = self.process(audio)
            if ok is not False:
                self.status = "idle"
        except Exception:
            traceback.print_exc()
            self.status = "error"
        finally:
            with self.lock:
                self.pending -= 1
                self._refresh_status()

    # ---- 録音後の処理（別スレッド）----
    def process(self, audio):
        dur = duration_sec(audio)
        if dur < self.b["min_record_sec"] or is_silent(audio):
            print(f"  （{dur:.1f}秒・無音のためスキップ）", flush=True)
            return
        dic = Dictionary.load(DICT_PATH)  # 毎回読むので辞書の編集がすぐ反映される
        t0 = time.time()
        raw, text, status, err = "", "", "ok", ""
        try:
            raw = self.engine.transcribe(to_wav_bytes(audio), dic)
            if not raw:
                print("  （聞き取れませんでした）", flush=True)
                return
            t1 = time.time()
            text = raw
            if self.b["cleanup"]:
                try:
                    text = self.engine.cleanup(raw, dic)
                except Exception as e:
                    status, err = "raw_only", f"整形エラー: {e}"
                    print(f"  {err}（文字起こしをそのまま入力します）", flush=True)
            text = dic.apply(text)
            print(f"  文字起こし {t1 - t0:.1f}秒 / 合計 {time.time() - t0:.1f}秒", flush=True)
            print(f"  生: {raw}", flush=True)
            print(f"  → {text}", flush=True)
        except Exception as e:
            status, err = "error", f"文字起こしエラー: {e}"
            self.history.add(raw, text, status, err, dur, self.engine.provider)
            self.sound("error")
            macos.notify("koe-input", err)
            print(f"  {err}", flush=True)
            self.status = "error"
            return False

        # 先に履歴に保存（貼り付けに失敗しても履歴ページから取り出せるように）
        self.history.add(raw, text, status, err, dur, self.engine.provider)
        self.last_text = text
        try:
            self.sm.wait_all_released()
            macos.paste_text(text, self.b["restore_clipboard"])
        except Exception as e:
            macos.notify("koe-input", f"貼り付けに失敗。履歴ページからコピーしてください: {e}")
            print(f"  貼り付けエラー: {e}", flush=True)


def single_instance_lock():
    """二重起動を防ぐ（2つ動くと1回の発話で2回入力されるため）。"""
    f = open(DATA_DIR / "koe.lock", "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return None
    return f


def check_permissions():
    """アクセシビリティの許可が無ければ知らせて、設定画面を開く。"""
    if not macos.IS_MAC:
        return
    try:
        from ApplicationServices import AXIsProcessTrusted
        trusted = bool(AXIsProcessTrusted())
    except Exception as e:
        print(f"（許可の確認ができませんでした: {e}）", flush=True)
        return
    print(f" アクセシビリティの許可: {'あり' if trusted else 'なし'}", flush=True)
    if not trusted:
        macos.notify("koe-input", "アクセシビリティと入力監視の許可が必要です。設定後、メニューの「再起動」を押してください")
        subprocess.Popen(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"])


def auto_update_loop(app: App, hours: float):
    time.sleep(60)  # 起動直後は避ける
    while True:
        try:
            updated, msg = updater.check_and_update()
            print(f"[アップデート確認] {msg}", flush=True)
            if updated:
                macos.notify("koe-input", f"アップデートしました（{msg}）")
                app.restart_requested = True  # 使っていないタイミングで自動で再起動
                return
        except Exception as e:
            print(f"[アップデート確認] 失敗: {e}", flush=True)
        time.sleep(max(hours, 0.5) * 3600)


def main():
    ensure_user_files()
    lock = single_instance_lock()
    if lock is None:
        macos.notify("koe-input", "すでに起動しています（メニューバーの 🎙 を確認してください）")
        print("すでに起動しています", flush=True)
        sys.exit(0)

    try:
        cfg = load_config()
    except ConfigError as e:
        macos.notify("koe-input 設定エラー", str(e))
        print(f"設定エラー: {e}", flush=True)
        if macos.IS_MAC:
            subprocess.Popen(["open", "-e", str(CONFIG_PATH)])
        sys.exit(0)

    app = App(cfg)
    port = cfg["behavior"]["history_port"]
    hist = f"http://127.0.0.1:{port}"
    try:
        serve(app.history, port)
    except OSError as e:
        print(f"履歴ページを起動できません: {e}", flush=True)

    mode = "押して離す→話す→もう一度押す" if cfg["behavior"]["mode"] == "toggle" else "押している間だけ録音"
    print("=" * 50)
    print(f" koe-input 起動しました（バージョン {updater.local_version()[:7] or '開発版'}）")
    print(f" サービス: {cfg['provider']}  ({app.engine.stt_model} / {app.engine.llm_model})")
    print(f" 操作: Option+Command（{mode}）/ Esc で取消")
    print(f" 履歴ページ: {hist}")
    print("=" * 50, flush=True)

    check_permissions()
    listener = KeyListener(app.sm)
    listener.start()

    if cfg["update"]["auto"]:
        threading.Thread(
            target=auto_update_loop, args=(app, cfg["update"]["check_interval_hours"]), daemon=True
        ).start()

    try:
        from .menubar import run_menubar
    except Exception as e:
        print(f"（メニューバー表示なしで動作します: {e}）", flush=True)
        run_menubar = None

    if run_menubar:
        run_menubar(app, hist)  # ここで止まり続ける。終了・再起動はメニュー側で行う
    else:
        try:
            while True:
                time.sleep(0.5)
                if app.restart_requested and app.is_idle():
                    os._exit(42)
        except KeyboardInterrupt:
            print("\n終了します")
            os._exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        sys.exit(1)
