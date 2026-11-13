"""見張り役・マイク再試行・状態リセットの確認。"""
import sys, types
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np
from koe.health import Watchdog
from koe.hotkey import HotkeyStateMachine
from koe import recorder as R

# ---- Watchdog
class FakeApp:
    def __init__(self): self.reasons=[]; self.recording=False; self.rec_started=0; self.stopped=0
    def request_restart(self, r): self.reasons.append(r)
    def auto_stop(self): self.stopped += 1; self.recording=False
clk={"wall":1000.0,"mono":50.0}; alive={"v":True}
app=FakeApp()
w=Watchdog(app, lambda: alive["v"], wall=lambda: clk["wall"], mono=lambda: clk["mono"], max_record_sec=600)
clk["wall"]+=5; clk["mono"]+=5; w.check(); assert app.reasons==[]                 # 普通に時間が進む
clk["wall"]+=3600; clk["mono"]+=5; w.check(); assert "スリープ" in app.reasons[0]  # スリープ
alive["v"]=False; clk["wall"]+=5; clk["mono"]+=5; w.check(); assert "ホットキー" in app.reasons[-1]
alive["v"]=True; app.recording=True; app.rec_started=clk["mono"]; clk["wall"]+=601; clk["mono"]+=601; w.check()
assert app.stopped==1
print("watchdog ok", app.reasons)

# ---- マイク再試行: 1回目失敗→読み直し→成功 / 3回とも失敗→例外
calls={"open":0,"init":0,"term":0}
class FakeStream:
    def __init__(self, **kw):
        calls["open"]+=1
        if calls["open"] <= calls["fail"]: raise RuntimeError("PaErrorCode -9986")
    def start(self): pass
    def stop(self): pass
    def close(self): pass
sd=types.SimpleNamespace(InputStream=FakeStream, query_devices=lambda kind: {"name":"MacBook Air Mic"},
    _terminate=lambda: calls.__setitem__("term",calls["term"]+1), _initialize=lambda: calls.__setitem__("init",calls["init"]+1))
sys.modules["sounddevice"]=sd
R.time.sleep=lambda s: None
calls["fail"]=1; r=R.Recorder(); r.start(); assert calls["open"]==2 and calls["init"]==1
r.stop()
calls.update(open=0,init=0,term=0,fail=99)
try: R.Recorder().start(); raise SystemExit("should raise")
except RuntimeError: pass
assert calls["open"]==3 and calls["init"]==2
print("mic retry ok")

# ---- 状態リセット: 録音開始に失敗→reset→次の1回で普通に録音開始できる
log=[]; t=[0]
sm=HotkeyStateMachine(lambda: log.append("start"), lambda: log.append("stop"), lambda: log.append("cancel"), 1e9, lambda: t[0])
sm.press("alt"); sm.press("cmd"); sm.reset(); sm.release("cmd"); sm.release("alt")
assert sm.state=="idle"
sm.press("alt"); sm.press("cmd"); assert log==["start","start"], log
print("reset ok")
print("HEALTH OK")
