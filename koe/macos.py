"""Mac 固有の操作: クリップボード、貼り付け(Cmd+V)、効果音、通知。"""
import os
import subprocess
import sys
import time

IS_MAC = sys.platform == "darwin"
# pbcopy/pbpaste は文字コード指定が無いと日本語が化けるため UTF-8 を指定する
_ENV = {**os.environ, "LANG": "en_US.UTF-8", "LC_ALL": "en_US.UTF-8"}


def get_clipboard() -> str:
    if not IS_MAC:
        return ""
    return subprocess.run(["pbpaste"], capture_output=True, env=_ENV).stdout.decode("utf-8", "replace")


def set_clipboard(text: str):
    if not IS_MAC:
        return
    subprocess.run(["pbcopy"], input=text.encode("utf-8"), env=_ENV, check=True)


KEYCODE_V = 9  # キーボード上の「V」の位置を表す番号（JIS・US 配列共通）


def press_paste():
    """Cmd+V を送って、いまカーソルがある場所に貼り付ける。

    以前は pynput で送っていたが、文字→キー番号の変換で Mac の入力ソース機能を
    メイン スレッド以外から呼ぶため、アプリが落ちることがあった。
    キー番号を直接指定して Mac の仕組み(Quartz)で送ることで、その変換を通らないようにしている。
    """
    import Quartz

    src = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateCombinedSessionState)
    for down in (True, False):
        ev = Quartz.CGEventCreateKeyboardEvent(src, KEYCODE_V, down)
        Quartz.CGEventSetFlags(ev, Quartz.kCGEventFlagMaskCommand)
        Quartz.CGEventPost(Quartz.kCGAnnotatedSessionEventTap, ev)
        time.sleep(0.02)


def paste_text(text: str, restore_clipboard: bool = False):
    old = get_clipboard() if restore_clipboard else None
    set_clipboard(text)
    time.sleep(0.05)
    press_paste()
    if restore_clipboard and old is not None:
        time.sleep(0.4)  # 貼り付け先アプリが読み終わるのを待ってから戻す
        set_clipboard(old)


SOUNDS = {
    "start": "/System/Library/Sounds/Tink.aiff",
    "stop": "/System/Library/Sounds/Pop.aiff",
    "cancel": "/System/Library/Sounds/Bottle.aiff",
    "error": "/System/Library/Sounds/Basso.aiff",
}


def play(name: str):
    if IS_MAC and name in SOUNDS:
        subprocess.Popen(["afplay", SOUNDS[name]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def notify(title: str, message: str):
    if not IS_MAC:
        print(f"[通知] {title}: {message}")
        return
    msg = message.replace('"', "'")[:200]
    subprocess.Popen(
        ["osascript", "-e", f'display notification "{msg}" with title "{title}"'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
