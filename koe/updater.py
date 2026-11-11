"""GitHub から新しいプログラムを取ってきて置き換える（自動アップデート）。

- 取得先は .repo ファイル（install.sh が書く。例: "username/koe-input"）
- いま入っている版は .version ファイル（GitHub の commit ID = 版ごとの識別番号）
- 自分で編集するファイル（config.toml, dictionary.txt, data/）は上書きしない
"""
import io
import shutil
import tempfile
import zipfile
from pathlib import Path

import httpx  # openai の部品として入っている通信ライブラリ（証明書の設定込みで動く）

from .config import ROOT

BRANCH = "main"
PROTECTED = {"config.toml", "dictionary.txt", "data", ".venv", ".version", ".repo", ".git"}


def repo() -> str:
    p = ROOT / ".repo"
    return p.read_text().strip() if p.exists() else ""


def local_version() -> str:
    p = ROOT / ".version"
    return p.read_text().strip() if p.exists() else ""


def remote_version(repo_name: str) -> str:
    r = httpx.get(
        f"https://api.github.com/repos/{repo_name}/commits/{BRANCH}",
        headers={"Accept": "application/vnd.github.sha"},
        timeout=15,
    )
    r.raise_for_status()
    return r.text.strip()


def apply_zip(zip_bytes: bytes, dest: Path, sha: str):
    with tempfile.TemporaryDirectory() as td:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            z.extractall(td)
        tops = [p for p in Path(td).iterdir() if p.is_dir()]
        if len(tops) != 1 or not (tops[0] / "koe" / "__main__.py").exists():
            raise RuntimeError("ダウンロードした内容が想定と違うため、更新を中止しました")
        src = tops[0]
        for f in src.rglob("*"):
            rel = f.relative_to(src)
            if rel.parts[0] in PROTECTED or f.is_dir():
                continue
            _replace_file(f, dest / rel)
    (dest / ".version").write_text(sha)


def _replace_file(src: Path, target: Path):
    """一時ファイルに書いてから差し替える。
    実行中のスクリプト(run.sh)を直接上書きすると動作がおかしくなるため、この方法にしている。"""
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp-update")
    shutil.copyfile(src, tmp)
    if target.suffix == ".sh":
        tmp.chmod(0o755)
    tmp.replace(target)


def check_and_update() -> tuple[bool, str]:
    """新しい版があれば取り込む。戻り値: (更新したか, 説明)"""
    name = repo()
    if not name:
        return False, "更新元(.repo)が未設定"
    remote = remote_version(name)
    if remote == local_version():
        return False, f"最新です（{remote[:7]}）"
    r = httpx.get(f"https://codeload.github.com/{name}/zip/{remote}", timeout=60, follow_redirects=True)
    r.raise_for_status()
    apply_zip(r.content, ROOT, remote)
    return True, f"{remote[:7]} に更新しました"
