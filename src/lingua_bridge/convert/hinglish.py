"""Hinglish (Roman Hindi) -> Devanagari, behind a small backend interface.

Roman Hindi spelling is not standardized ("kaise", "kese", "kaisay"), so this is spelling
prediction, never an exact mapping. Two engines:

* RuleBasedBackend: offline, deterministic, no extra dependencies. A lexicon of common words
  plus transliteration rules for the rest. This is the default.
* Ai4BharatBackend: the neural IndicXlit engine (`pip install "lingua-bridge[xlit]"`). Its
  dependencies (fairseq and others) often fail to install on modern Python, so it is optional.
  Selecting backend "auto" uses it only when it imports cleanly, otherwise the rule engine.
"""

from __future__ import annotations

import logging
import re
from typing import Protocol

from indic_transliteration import sanscript

from ..config import get_settings
from ..errors import ConversionError
from ._hinglish_lexicon import LEXICON

log = logging.getLogger(__name__)


class HinglishBackend(Protocol):
    name: str

    def convert(self, text: str) -> str: ...


_TOKEN = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?|\d+|\s+|.", re.S)
_TRAILING_VIRAMA = re.compile("्(?=$)")


def _to_itrans(word: str) -> str:
    """Normalize common Hinglish spelling habits into ITRANS."""
    w = word.lower()
    w = w.replace("ph", "\x01").replace("f", "ph").replace("\x01", "ph")
    w = w.replace("chh", "\x02").replace("ch", "\x03")
    w = w.replace("c", "k").replace("q", "k").replace("x", "ks").replace("z", "j").replace("w", "v")
    w = w.replace("\x02", "chh").replace("\x03", "ch")
    w = w.replace("ee", "ii").replace("oo", "uu").replace("ou", "au")
    w = w.replace("ai", "ai").replace("ei", "ai")
    if len(w) > 2 and w.endswith("a") and not w.endswith("aa"):
        w = w[:-1] + "aa"  # final -a is usually the long vowel ा in Hindi
    if len(w) > 2 and w.endswith("i") and not w.endswith("ii"):
        w = w[:-1] + "ii"  # final -i is usually ी
    if w.endswith("ain"):
        w = w[:-3] + "aiM"
    return w


class RuleBasedBackend:
    name = "rule"

    def __init__(self) -> None:
        self._lexicon = LEXICON

    def _word(self, word: str) -> str:
        key = word.lower()
        if key in self._lexicon:
            return self._lexicon[key]
        deva = sanscript.transliterate(_to_itrans(word), sanscript.ITRANS, sanscript.DEVANAGARI)
        return _TRAILING_VIRAMA.sub("", deva)  # Hindi drops the final inherent vowel

    def convert(self, text: str) -> str:
        out = []
        for tok in _TOKEN.findall(text):
            out.append(self._word(tok) if tok[0].isascii() and tok[0].isalpha() else tok)
        return "".join(out)


class Ai4BharatBackend:
    """Neural transliteration via ai4bharat-transliteration. Untested in this repo's CI."""

    name = "ai4bharat"

    def __init__(self) -> None:
        try:
            from ai4bharat.transliteration import XlitEngine  # type: ignore[import-not-found]
        except Exception as exc:  # ImportError, or a broken transitive dependency
            raise ConversionError(
                "ai4bharat-transliteration is not usable here "
                f"({type(exc).__name__}: {exc}). Use LB_HINGLISH_BACKEND=rule."
            ) from exc
        self._engine = XlitEngine("hi", beam_width=10, src_script_type="en")

    def convert(self, text: str) -> str:
        result = self._engine.translit_sentence(text)
        return result["hi"] if isinstance(result, dict) else str(result)


_cache: dict[str, HinglishBackend] = {}


def get_backend(name: str | None = None) -> HinglishBackend:
    """Return the configured backend; 'auto' prefers ai4bharat when importable."""
    name = name or get_settings().hinglish_backend
    if name in _cache:
        return _cache[name]
    backend: HinglishBackend
    if name == "rule":
        backend = RuleBasedBackend()
    elif name == "ai4bharat":
        backend = Ai4BharatBackend()
    elif name == "auto":
        try:
            backend = Ai4BharatBackend()
        except ConversionError as exc:
            log.debug("Hinglish: falling back to the rule-based backend (%s)", exc)
            backend = RuleBasedBackend()
    else:
        raise ConversionError(f"Unknown Hinglish backend {name!r} (use auto, rule or ai4bharat).")
    _cache[name] = backend
    return backend


def hinglish_to_devanagari(text: str, backend: str | None = None) -> str:
    return get_backend(backend).convert(text)
