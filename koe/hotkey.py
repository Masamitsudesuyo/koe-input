"""ホットキー(Option + Command)の判定。

動作:
- Option と Command を両方押している間だけ録音 → 離したら入力（押しっぱなしモード）
- 短く押してすぐ離す → 録音が続く（トグルモード）。もう一度 Option+Command で終了、Esc で取り消し
- 押している途中で他のキーを押した場合は、別のショートカット操作とみなして取り消し

キーの種類を "cmd" / "alt" / "esc" / "other" の4種類に単純化して判定する。
pynput への依存は KeyListener 側だけにして、判定部分(HotkeyStateMachine)は単体でテストできるようにしている。
"""
import threading
import time

IDLE, HOLD, TOGGLE = "idle", "hold", "toggle"


class HotkeyStateMachine:
    def __init__(self, on_start, on_stop, on_cancel, tap_threshold=0.35, clock=time.monotonic):
        self.on_start, self.on_stop, self.on_cancel = on_start, on_stop, on_cancel
        self.tap_threshold = tap_threshold
        self.clock = clock
        self.state = IDLE
        self.down = set()           # 押されている修飾キー {"cmd", "alt"}
        self.wait_release = False   # 終了操作の後、一度両方離すまで再開しない
        self.t0 = 0.0
        self.released = threading.Event()
        self.released.set()

    def _combo(self):
        return "cmd" in self.down and "alt" in self.down

    def press(self, k: str):
        if k in ("cmd", "alt"):
            self.down.add(k)
            self.released.clear()
            if not self._combo():
                return
            if self.state == IDLE and not self.wait_release:
                self.state, self.t0 = HOLD, self.clock()
                self.on_start()
            elif self.state == TOGGLE:
                self.state, self.wait_release = IDLE, True
                self.on_stop()
        elif k == "esc" and self.state in (HOLD, TOGGLE):
            self.state, self.wait_release = IDLE, bool(self.down)
            self.on_cancel()
        elif k != "esc" and self.state == HOLD:
            # Option+Command+何か = 別のショートカットなので録音を捨てる
            self.state, self.wait_release = IDLE, True
            self.on_cancel()

    def release(self, k: str):
        if k not in ("cmd", "alt"):
            return
        self.down.discard(k)
        if self.state == HOLD:
            if self.clock() - self.t0 < self.tap_threshold:
                self.state = TOGGLE
            else:
                self.state, self.wait_release = IDLE, True
                self.on_stop()
        if not self.down:
            self.wait_release = False
            self.released.set()

    def wait_all_released(self, timeout=2.0):
        """貼り付け(Cmd+V)を送る前に、Option/Command が離されるのを待つ。"""
        self.released.wait(timeout)


class KeyListener:
    """pynput でキーボードを監視し、HotkeyStateMachine に渡す（Mac で動かす部分）。"""

    def __init__(self, sm: HotkeyStateMachine):
        from pynput import keyboard

        self.kb = keyboard
        self.sm = sm
        K = keyboard.Key
        self.cmd_keys = {K.cmd, K.cmd_l, K.cmd_r}
        self.alt_keys = {K.alt, K.alt_l, K.alt_r, getattr(K, "alt_gr", K.alt)}
        self.listener = keyboard.Listener(on_press=self._p, on_release=self._r)

    def _kind(self, key):
        if key in self.cmd_keys:
            return "cmd"
        if key in self.alt_keys:
            return "alt"
        if key == self.kb.Key.esc:
            return "esc"
        return "other"

    def _p(self, key):
        self.sm.press(self._kind(key))

    def _r(self, key):
        self.sm.release(self._kind(key))

    def start(self):
        self.listener.start()

    def join(self):
        self.listener.join()
