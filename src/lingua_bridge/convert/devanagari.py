"""Devanagari <-> IAST / Harvard-Kyoto / ITRANS / casual Roman.

Transliteration changes the writing system, not the language. IAST, HK and ITRANS each map
one-to-one onto Devanagari for standard Sanskrit text, so converting there and back is
lossless. "roman" is a casual, diacritic-free spelling: it is one-way and lossy by design.
"""

from __future__ import annotations

import unicodedata
from enum import StrEnum

from indic_transliteration import sanscript

from ..errors import ConversionError
from ..schemas import Fidelity


class Scheme(StrEnum):
    DEVANAGARI = "devanagari"
    IAST = "iast"
    HK = "hk"
    ITRANS = "itrans"
    ROMAN = "roman"  # casual, lossy


_SANSCRIPT = {
    Scheme.DEVANAGARI: sanscript.DEVANAGARI,
    Scheme.IAST: sanscript.IAST,
    Scheme.HK: sanscript.HK,
    Scheme.ITRANS: sanscript.ITRANS,
}
_LOSSLESS = set(_SANSCRIPT)

_ALIASES = {
    "deva": "devanagari", "nagari": "devanagari",
    "harvard-kyoto": "hk", "harvardkyoto": "hk", "harvard_kyoto": "hk",
    "latin": "roman", "casual": "roman",
}  # fmt: skip


def parse_scheme(value: str | Scheme) -> Scheme:
    if isinstance(value, Scheme):
        return value
    key = value.strip().lower()
    key = _ALIASES.get(key, key)
    try:
        return Scheme(key)
    except ValueError:
        valid = ", ".join(s.value for s in Scheme)
        raise ConversionError(f"Unknown scheme {value!r}. Valid schemes: {valid}.") from None


def fidelity_for(src: Scheme, tgt: Scheme) -> Fidelity:
    """How faithfully a src->tgt conversion can be reversed."""
    if src == tgt:
        return "lossless"
    if src in _LOSSLESS and tgt in _LOSSLESS:
        return "lossless"
    if tgt == Scheme.ROMAN:
        return "lossy"
    return "best_effort"  # roman -> anything: spelling is not standardized


# Casual Roman: derived from IAST by dropping diacritics the way people type informally.
_ROMAN_MAP = {
    "ā": "a", "ī": "i", "ū": "u", "ṛ": "ri", "ṝ": "ri", "ḷ": "l", "ḹ": "l",
    "ṃ": "m", "ṁ": "m", "ḥ": "h", "ś": "sh", "ṣ": "sh", "ṭ": "t", "ḍ": "d",
    "ṇ": "n", "ṅ": "n", "ñ": "n", "ē": "e", "ō": "o",
    "Ā": "A", "Ī": "I", "Ū": "U", "Ś": "Sh", "Ṣ": "Sh", "Ṭ": "T", "Ḍ": "D", "Ṇ": "N",
}  # fmt: skip


def _iast_to_casual_roman(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    return "".join(_ROMAN_MAP.get(ch, ch) for ch in text)


def transliterate(text: str, src: str | Scheme, tgt: str | Scheme) -> str:
    """Convert text between schemes. Raises ConversionError for unknown schemes."""
    s, t = parse_scheme(src), parse_scheme(tgt)
    if s == t:
        return text
    if s == Scheme.ROMAN:
        # Casual Roman input is spelling prediction, not a mapping: use the Hinglish engine.
        from .hinglish import hinglish_to_devanagari

        deva = hinglish_to_devanagari(text)
        return deva if t == Scheme.DEVANAGARI else transliterate(deva, Scheme.DEVANAGARI, t)
    if t == Scheme.ROMAN:
        iast = sanscript.transliterate(text, _SANSCRIPT[s], sanscript.IAST)
        return _iast_to_casual_roman(iast)
    return sanscript.transliterate(text, _SANSCRIPT[s], _SANSCRIPT[t])


def to_devanagari(text: str, src: str | Scheme) -> str:
    return transliterate(text, src, Scheme.DEVANAGARI)
