"""偽のAPIサーバーを立てて、Engine と App.process の流れを確認する。"""
import sys, json, threading, time, tempfile
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np
seen = {}
class H(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        if self.path.endswith("/audio/transcriptions"):
            seen["stt"] = body
            out = {"text": "えーっとくろーどに明日の3時じゃなかった4時って伝えて"}
        else:
            seen["llm"] = json.loads(body)
            out = {"id":"x","object":"chat.completion","created":0,"model":"m","choices":[{"index":0,"finish_reason":"stop","message":{"role":"assistant","content":"クロードに明日の4時と伝えて"}}]}
        b = json.dumps(out, ensure_ascii=False).encode()
        self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers(); self.wfile.write(b)
    def log_message(self,*a): pass
srv = ThreadingHTTPServer(("127.0.0.1", 18999), H); threading.Thread(target=srv.serve_forever, daemon=True).start()

import koe.engine as E
E.BASE_URLS["groq"] = "http://127.0.0.1:18999/v1"
import koe.__main__ as M
import koe.config
pasted = []
M.macos.paste_text = lambda t, r: pasted.append(t)
td = tempfile.mkdtemp(); M.DATA_DIR = Path(td)
cfg = {"provider":"groq","language":"ja",
       "groq":{"api_key":"k","stt_model":"whisper-large-v3-turbo","llm_model":"openai/gpt-oss-120b","llm_reasoning_effort":"low"},
       "update":{"auto":False,"check_interval_hours":6},"behavior":{"mode":"toggle","cleanup":True,"tap_threshold_sec":0.35,"min_record_sec":0.4,"restore_clipboard":False,"sounds":False,"history_port":0}}
M.DICT_PATH = Path("dictionary.example.txt")
app = M.App(cfg)
loud = (np.sin(np.arange(32000)/5)*3000).astype(np.int16)
app.process(loud)
assert pasted == ["Claudeに明日の4時と伝えて"], pasted   # 辞書置換(クロード→Claude)が最後に効く
assert seen["llm"]["reasoning_effort"] == "low" and seen["llm"]["temperature"] == 0
assert "用語辞書" in seen["llm"]["messages"][0]["content"]
assert b'name="language"' in seen["stt"] and "Claude".encode() in seen["stt"] and b"RIFF" in seen["stt"]
rows = app.history.list(); assert rows[0]["status"] == "ok" and rows[0]["raw"].startswith("えーっと")
# short / silent audio skipped
app.process(np.zeros(32000, dtype=np.int16)); app.process(loud[:1000]); assert len(pasted) == 1
# LLM failure -> raw pasted
E.BASE_URLS["groq"]="http://127.0.0.1:18999/v1"
app.engine.cleanup = lambda raw, d: (_ for _ in ()).throw(RuntimeError("boom"))
app.process(loud); assert pasted[-1].startswith("えーっとClaude"), pasted
assert app.history.list()[0]["status"] == "raw_only"
print("E2E OK"); print(pasted)
