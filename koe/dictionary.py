"""辞書ファイルの読み込みと置換。"""
import re
from pathlib import Path


class Dictionary:
    def __init__(self, terms: list[str], replacements: list[tuple[str, str]]):
        self.terms = terms                # AI へのヒントにする正しい表記
        self.replacements = replacements  # (間違い, 正しい) の組

    @classmethod
    def load(cls, path: Path) -> "Dictionary":
        terms, reps = [], []
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=>" in line:
                    wrong, right = (s.strip() for s in line.split("=>", 1))
                    if wrong and right:
                        reps.append((wrong, right))
                        if right not in terms:
                            terms.append(right)
                elif line not in terms:
                    terms.append(line)
        # 英字の語は、大文字小文字の違いを自動で辞書表記にそろえる（github → GitHub）
        for t in terms:
            if t.isascii() and any(c.isalpha() for c in t) and all(w != t for w, _ in reps):
                reps.append((t, t))
        # 長い語から先に置換する（短い語が長い語の一部を壊さないように）
        reps.sort(key=lambda r: len(r[0]), reverse=True)
        return cls(terms, reps)

    def apply(self, text: str) -> str:
        for wrong, right in self.replacements:
            if wrong.isascii():
                # 英字: 大文字小文字を無視し、英数字の途中ではマッチさせない
                pat = r"(?<![A-Za-z0-9])" + re.escape(wrong) + r"(?![A-Za-z0-9])"
                text = re.sub(pat, lambda m: right, text, flags=re.IGNORECASE)
            else:
                text = text.replace(wrong, right)
        return text

    def stt_prompt(self, max_chars: int = 300) -> str:
        """音声認識モデルに渡すヒント文。長すぎるとモデルが受け付けないので切る。"""
        if not self.terms:
            return ""
        out = "、".join(self.terms)
        return out[:max_chars]
