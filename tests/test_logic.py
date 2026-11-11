import sys, json, urllib.request, time, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np
from koe.dictionary import Dictionary
from koe.hotkey import HotkeyStateMachine
from koe.recorder import to_wav_bytes, is_silent
from koe.engine import Engine
from koe.history import History, serve

# --- dictionary
d = Dictionary.load(Path("dictionary.example.txt"))
assert "Claude" in d.terms and "GitHub" in d.terms
assert d.apply("くろーどとgithubでgithubsは別") == "ClaudeとGitHubでgithubsは別", d.apply("くろーどとgithubでgithubsは別")
print("dict ok:", d.stt_prompt())

# --- hotkey state machine
class Clock:
    t = 0.0
    def __call__(self): return self.t
def mk():
    log=[]; c=Clock()
    sm=HotkeyStateMachine(lambda:log.append("start"),lambda:log.append("stop"),lambda:log.append("cancel"),0.35,c)
    return sm,log,c
# hold
sm,log,c=mk(); sm.press("alt"); sm.press("cmd"); c.t=2; sm.release("cmd"); sm.release("alt"); assert log==["start","stop"],log
# tap -> toggle -> combo stops
sm,log,c=mk(); sm.press("cmd"); sm.press("alt"); c.t=0.1; sm.release("alt"); sm.release("cmd")
assert log==["start"] and sm.state=="toggle"
c.t=5; sm.press("other"); assert sm.state=="toggle"   # typing during toggle doesn't cancel
sm.press("cmd"); sm.press("alt"); assert log==["start","stop"]
c.t=6; sm.release("alt"); sm.release("cmd"); assert log==["start","stop"] and sm.state=="idle"  # no restart on release
# toggle -> esc
sm,log,c=mk(); sm.press("cmd"); sm.press("alt"); c.t=0.1; sm.release("alt"); sm.release("cmd"); sm.press("esc"); assert log==["start","cancel"]
# other shortcut (cmd+opt+esc / cmd+opt+i) cancels
sm,log,c=mk(); sm.press("cmd"); sm.press("alt"); sm.press("other"); c.t=1; sm.release("alt"); sm.release("cmd"); assert log==["start","cancel"],log
# cmd alone does nothing
sm,log,c=mk(); sm.press("cmd"); sm.press("other"); sm.release("cmd"); assert log==[]
# after stop, re-arm works
sm,log,c=mk(); sm.press("alt"); sm.press("cmd"); c.t=1; sm.release("cmd"); sm.press("cmd"); assert log==["start","stop"]  # still holding alt: no restart
sm.release("cmd"); sm.release("alt"); sm.press("alt"); sm.press("cmd"); assert log==["start","stop","start"]
assert sm.released.is_set() is False
print("hotkey ok")

# --- audio
sil=np.zeros(16000,dtype=np.int16); loud=(np.sin(np.arange(16000)/5)*3000).astype(np.int16)
assert is_silent(sil) and not is_silent(loud)
w=to_wav_bytes(loud); assert w[:4]==b"RIFF" and len(w)==44+32000
print("audio ok")

# --- hallucination filter
assert Engine._drop_hallucination("ご視聴ありがとうございました", "")==""
assert Engine._drop_hallucination("明日は晴れ","")=="明日は晴れ"
assert Engine._drop_hallucination("Claude、GitHub","Claude、GitHub")==""

# --- history + web
with tempfile.TemporaryDirectory() as td:
    h=History(Path(td)/"h.db")
    h.add("えーっと明日3時じゃなかった4時","明日4時に集合","ok","",2.0,"groq")
    h.add("テスト<script>","","error","文字起こしエラー: timeout",1.0,"groq")
    serve(h, 18765); time.sleep(0.2)
    page=urllib.request.urlopen("http://127.0.0.1:18765/").read().decode()
    assert "明日4時に集合" in page and "<script>" not in page.split("<main>")[1].split("<script>\ndocument")[0]
    js=json.loads(urllib.request.urlopen("http://127.0.0.1:18765/api/history?q=%E6%98%8E%E6%97%A5").read())
    assert len(js)==1
    open(Path(td)/"page.html","w").write(page)
    import shutil; shutil.copy(Path(td)/"page.html","/tmp/claude-0/page.html") if Path("/tmp/claude-0").exists() else None
print("history ok")
print("ALL OK")
