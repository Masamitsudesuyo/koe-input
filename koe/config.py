"""設定ファイル(config.toml)の読み込み。"""
import shutil
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.toml"
DICT_PATH = ROOT / "dictionary.txt"
DATA_DIR = ROOT / "data"


class ConfigError(Exception):
    pass


def ensure_user_files():
    """自分で編集するファイルが無ければ、ひな形からコピーして作る。"""
    if not DICT_PATH.exists() and (ROOT / "dictionary.example.txt").exists():
        shutil.copy(ROOT / "dictionary.example.txt", DICT_PATH)
    if not CONFIG_PATH.exists() and (ROOT / "config.example.toml").exists():
        shutil.copy(ROOT / "config.example.toml", CONFIG_PATH)
    DATA_DIR.mkdir(exist_ok=True)


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise ConfigError("config.toml がありません。")
    with open(CONFIG_PATH, "rb") as f:
        try:
            cfg = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise ConfigError(f"config.toml の書き方に誤りがあります: {e}")

    provider = cfg.get("provider", "groq")
    if provider not in ("groq", "openai"):
        raise ConfigError(f'provider は "groq" か "openai" にしてください（今は "{provider}"）')
    p = cfg.get(provider, {})
    if not p.get("api_key"):
        raise ConfigError(f"config.toml の [{provider}] の api_key が空です。API キーを貼ってください。")

    b = cfg.setdefault("behavior", {})
    b.setdefault("mode", "toggle")       # "toggle" = 押して離す→話す→もう一度押す / "hold" = 押している間だけ録音
    b.setdefault("cleanup", True)
    b.setdefault("tap_threshold_sec", 0.35)
    b.setdefault("min_record_sec", 0.4)
    b.setdefault("restore_clipboard", False)
    b.setdefault("sounds", True)
    b.setdefault("history_port", 8765)
    u = cfg.setdefault("update", {})
    u.setdefault("auto", True)
    u.setdefault("check_interval_hours", 6)
    cfg.setdefault("language", "ja")
    return cfg
