"""Chinese conversions: pinyin (pypinyin) and Simplified <-> Traditional (OpenCC).

Both are lossy or best-effort by nature. Pinyin has far fewer syllables than characters, and
several traditional characters merged into one simplified character.
"""

from __future__ import annotations

import re
from enum import StrEnum
from functools import lru_cache

import pypinyin
from opencc import OpenCC


class PinyinStyle(StrEnum):
    MARKS = "marks"  # nǐ hǎo
    NUMBERS = "numbers"  # ni3 hao3
    PLAIN = "plain"  # ni hao


class ChineseVariant(StrEnum):
    STANDARD = "standard"  # s2t / t2s
    TAIWAN = "taiwan"  # s2twp / tw2sp, with Taiwan phrase conventions
    HONGKONG = "hongkong"  # s2hk / hk2s


_STYLES = {
    PinyinStyle.MARKS: pypinyin.Style.TONE,
    PinyinStyle.NUMBERS: pypinyin.Style.TONE3,
    PinyinStyle.PLAIN: pypinyin.Style.NORMAL,
}
_TO_TRAD = {
    ChineseVariant.STANDARD: "s2t",
    ChineseVariant.TAIWAN: "s2twp",
    ChineseVariant.HONGKONG: "s2hk",
}
_TO_SIMP = {
    ChineseVariant.STANDARD: "t2s",
    ChineseVariant.TAIWAN: "tw2sp",
    ChineseVariant.HONGKONG: "hk2s",
}
_PUNCT = str.maketrans(
    {"，": ",", "。": ".", "！": "!", "？": "?", "；": ";", "：": ":", "、": ",",
     "（": "(", "）": ")", "“": '"', "”": '"', "‘": "'", "’": "'", "《": "<", "》": ">"}
)  # fmt: skip
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([,.!?;:)>])")
_SPACE_AFTER_OPEN = re.compile(r"([(<])\s+")


@lru_cache(maxsize=8)
def _cc(config: str) -> OpenCC:
    return OpenCC(config)


def to_pinyin(text: str, style: PinyinStyle | str = PinyinStyle.MARKS) -> str:
    """Hanzi to pinyin, words separated by spaces. Non-Chinese text passes through."""
    style = PinyinStyle(style)
    parts = [p[0] for p in pypinyin.pinyin(text, style=_STYLES[style], errors="default")]
    out = " ".join(p for p in parts if p.strip())
    out = out.translate(_PUNCT)
    out = _SPACE_BEFORE_PUNCT.sub(r"\1", out)
    return _SPACE_AFTER_OPEN.sub(r"\1", out)


def to_traditional(text: str, variant: ChineseVariant | str = ChineseVariant.STANDARD) -> str:
    return _cc(_TO_TRAD[ChineseVariant(variant)]).convert(text)


def to_simplified(text: str, variant: ChineseVariant | str = ChineseVariant.STANDARD) -> str:
    return _cc(_TO_SIMP[ChineseVariant(variant)]).convert(text)


def script_counts(text: str) -> tuple[int, int]:
    """(characters that are simplified-only, characters that are traditional-only)."""
    s2t, t2s = _cc("s2t"), _cc("t2s")
    simp = trad = 0
    for ch in text:
        if not ("一" <= ch <= "鿿"):
            continue
        if s2t.convert(ch) != ch:
            simp += 1
        if t2s.convert(ch) != ch:
            trad += 1
    return simp, trad
