"""偽の GitHub サーバーを使い、自動アップデートが「設定・辞書・履歴を残したまま」差し替えるか確認する。"""
import io, sys, zipfile, tempfile, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import httpx
import koe.updater as U

root = Path(tempfile.mkdtemp())
(root/"koe").mkdir(); (root/"koe/__main__.py").write_text("OLD")
(root/"config.toml").write_text("MY KEY"); (root/"dictionary.txt").write_text("MY DICT")
(root/"data").mkdir(); (root/"data/history.db").write_text("MY HISTORY")
(root/"scripts").mkdir(); (root/"scripts/run.sh").write_text("old")
(root/".repo").write_text("me/koe-input"); (root/".version").write_text("aaa")
U.ROOT = root

buf = io.BytesIO()
with zipfile.ZipFile(buf, "w") as z:
    z.writestr("koe-input-bbb/koe/__main__.py", "NEW")
    z.writestr("koe-input-bbb/koe/new_module.py", "NEW2")
    z.writestr("koe-input-bbb/config.toml", "EVIL")       # 万一リポジトリに入っていても上書きしない
    z.writestr("koe-input-bbb/dictionary.txt", "EVIL")
    z.writestr("koe-input-bbb/scripts/run.sh", "new")
    z.writestr("koe-input-bbb/config.example.toml", "ex")
calls = []
def fake_get(url, **kw):
    calls.append(url)
    req = httpx.Request("GET", url)
    if "api.github.com" in url: return httpx.Response(200, text="bbb\n", request=req)
    return httpx.Response(200, content=buf.getvalue(), request=req)
U.httpx.get = fake_get

ino = (root/"scripts/run.sh").stat().st_ino
print(U.check_and_update())
assert (root/"koe/__main__.py").read_text()=="NEW" and (root/"koe/new_module.py").read_text()=="NEW2"
assert (root/"config.toml").read_text()=="MY KEY" and (root/"dictionary.txt").read_text()=="MY DICT"
assert (root/"data/history.db").read_text()=="MY HISTORY"
assert (root/"scripts/run.sh").read_text()=="new" and (root/"scripts/run.sh").stat().st_ino != ino  # 新しいファイルとして差し替え
assert (root/".version").read_text()=="bbb"
assert "me/koe-input" in calls[0] and calls[1].endswith("/zip/bbb")
print(U.check_and_update())   # 2回目は最新
assert len(calls)==3
# 壊れた zip は適用しない
bad = io.BytesIO(); zipfile.ZipFile(bad,"w").writestr("x/readme.txt","hi")
try: U.apply_zip(bad.getvalue(), root, "ccc"); raise SystemExit("should fail")
except RuntimeError as e: print("rejected:", e)
assert (root/".version").read_text()=="bbb"
print("UPDATER OK")
