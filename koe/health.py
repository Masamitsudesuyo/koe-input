"""見張り役（ウォッチドッグ）。アプリが「動いているのに使えない」状態を自動で直す。

5秒ごとに次を確認し、問題があれば「使っていないときに自動で再起動」を予約する。
再起動すると、マイク・キー監視・通信の部品がすべて新しく作り直されるため、
古い状態が原因の不具合（マイクが開けない、ホットキーが効かない等）はまとめて解消する。

1. Mac がスリープから復帰した
   → 判定方法: 普通の時計(time.time)はスリープ中も進むが、
     経過時間用の時計(time.monotonic)は Mac ではスリープ中に止まる。両者の差が開いたらスリープしていた。
2. キー監視（ホットキー）の部品が止まった
3. 録音しっぱなしで上限時間を超えた → 自動で録音を終えて入力する
4. 停止の操作をしたのに録音が終わらない（固まった） → すぐに強制的に起動し直す
"""
import threading
import time


class Watchdog:
    def __init__(self, app, listener_alive, interval=5.0, sleep_gap=30.0, max_record_sec=600, stuck_sec=10.0,
                 wall=time.time, mono=time.monotonic):
        self.app = app
        self.listener_alive = listener_alive   # キー監視が動いているかを返す関数
        self.interval = interval
        self.sleep_gap = sleep_gap
        self.max_record_sec = max_record_sec
        self.stuck_sec = stuck_sec
        self.wall, self.mono = wall, mono
        self._last_wall, self._last_mono = wall(), mono()

    def check(self):
        """1回分の確認。テストしやすいよう、ループとは分けている。"""
        now_wall, now_mono = self.wall(), self.mono()
        gap = (now_wall - self._last_wall) - (now_mono - self._last_mono)
        self._last_wall, self._last_mono = now_wall, now_mono

        if gap > self.sleep_gap:
            self.app.request_restart(f"スリープからの復帰を検知（約{int(gap)}秒停止）")
        if not self.listener_alive():
            self.app.request_restart("ホットキーの監視が止まっていた")
        stop_at = getattr(self.app, "stop_requested_at", 0.0)
        if self.app.recording and stop_at and now_mono - stop_at > self.stuck_sec:
            self.app.force_restart(f"停止の操作から{int(now_mono - stop_at)}秒たっても録音が終わらない")
            return
        if self.app.recording and now_mono - self.app.rec_started > self.max_record_sec:
            print(f"[見張り] 録音が{self.max_record_sec // 60}分を超えたため、自動で終了して入力します", flush=True)
            self.app.auto_stop()

    def loop(self):
        while True:
            time.sleep(self.interval)
            try:
                self.check()
            except Exception as e:
                print(f"[見張り] 確認中にエラー: {e}", flush=True)

    def start(self):
        threading.Thread(target=self.loop, daemon=True).start()
