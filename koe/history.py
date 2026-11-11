"""履歴の保存(SQLite = ファイル1つで動くデータベース)と、履歴を見るWebページ。"""
import html
import json
import sqlite3
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs


class History:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._lock = threading.Lock()
        with self._conn() as c:
            c.execute(
                """CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    raw TEXT, text TEXT, status TEXT, error TEXT,
                    duration REAL, provider TEXT
                )"""
            )

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def add(self, raw, text, status, error="", duration=0.0, provider=""):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._lock, self._conn() as c:
            c.execute(
                "INSERT INTO history (created_at, raw, text, status, error, duration, provider) VALUES (?,?,?,?,?,?,?)",
                (now, raw, text, status, error, duration, provider),
            )

    def list(self, limit=300, q=""):
        sql = "SELECT id, created_at, raw, text, status, error, duration FROM history"
        args = []
        if q:
            sql += " WHERE text LIKE ? OR raw LIKE ?"
            args = [f"%{q}%", f"%{q}%"]
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        with self._conn() as c:
            rows = c.execute(sql, args).fetchall()
        keys = ["id", "created_at", "raw", "text", "status", "error", "duration"]
        return [dict(zip(keys, r)) for r in rows]


PAGE = """<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>koe-input 履歴</title>
<style>
:root{--bg:#f6f6f4;--card:#fff;--fg:#1d1d1f;--sub:#6e6e73;--line:#e3e3e0;--acc:#2f6fed;--err:#c0392b}
@media(prefers-color-scheme:dark){:root{--bg:#18181a;--card:#232326;--fg:#ececec;--sub:#9a9aa0;--line:#333338;--acc:#6b9bff;--err:#ff6b5e}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 -apple-system,"Hiragino Sans",sans-serif}
main{max-width:760px;margin:0 auto;padding:24px 16px}
h1{font-size:20px;margin:0 0 12px}
form{display:flex;gap:8px;margin-bottom:16px}
input{flex:1;padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--fg);font-size:15px}
.item{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin-bottom:10px}
.meta{display:flex;justify-content:space-between;align-items:center;color:var(--sub);font-size:12px;margin-bottom:6px}
.text{white-space:pre-wrap;word-break:break-word}
.err{color:var(--err);font-size:13px}
button{border:1px solid var(--line);background:var(--bg);color:var(--fg);border-radius:6px;padding:3px 10px;font-size:12px;cursor:pointer}
button.done{background:var(--acc);color:#fff;border-color:var(--acc)}
details{margin-top:6px;color:var(--sub);font-size:13px}
</style></head><body><main>
<h1>koe-input 履歴</h1>
<form><input name="q" placeholder="検索" value="__Q__"><button>検索</button></form>
__ITEMS__
</main>
<script>
document.querySelectorAll('button[data-t]').forEach(b=>b.onclick=async()=>{
  const t=JSON.parse(b.dataset.t);
  try{await navigator.clipboard.writeText(t)}catch(e){const a=document.createElement('textarea');a.value=t;document.body.appendChild(a);a.select();document.execCommand('copy');a.remove()}
  b.textContent='コピーしました';b.classList.add('done');setTimeout(()=>{b.textContent='コピー';b.classList.remove('done')},1500)
});
</script></body></html>"""


def render(rows, q=""):
    items = []
    for r in rows:
        text = r["text"] or r["raw"] or ""
        status = {"ok": "", "raw_only": "（整形失敗・文字起こしのみ）", "error": "（失敗）"}.get(r["status"], "")
        err = f'<div class="err">{html.escape(r["error"])}</div>' if r["error"] else ""
        raw = ""
        if r["raw"] and r["raw"] != text:
            raw = f'<details><summary>文字起こし（整形前）</summary><div class="text">{html.escape(r["raw"])}</div></details>'
        copy = f'<button data-t="{html.escape(json.dumps(text, ensure_ascii=False))}">コピー</button>' if text else ""
        items.append(
            f'<div class="item"><div class="meta"><span>{r["created_at"]} {status}</span>{copy}</div>'
            f'<div class="text">{html.escape(text)}</div>{err}{raw}</div>'
        )
    if not items:
        items.append('<p style="color:var(--sub)">まだ履歴はありません。</p>')
    return PAGE.replace("__Q__", html.escape(q)).replace("__ITEMS__", "\n".join(items))


def serve(history: History, port: int):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            u = urlparse(self.path)
            q = parse_qs(u.query).get("q", [""])[0]
            if u.path == "/api/history":
                body = json.dumps(history.list(q=q), ensure_ascii=False).encode()
                ctype = "application/json; charset=utf-8"
            elif u.path == "/":
                body = render(history.list(q=q), q).encode()
                ctype = "text/html; charset=utf-8"
            else:
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    # 127.0.0.1 = 自分の Mac からしか開けない設定（他人からは見えない）
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv
