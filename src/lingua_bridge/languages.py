"""Single registry of supported languages.

Every module imports this instead of repeating string codes. Models disagree on codes
(ISO 639, FLORES-200, NLLB tags), so the translation between them lives here only.
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import UnknownLanguageError


@dataclass(frozen=True)
class Language:
    code: str  # the short code users type: sa, hi, en, zh
    flores: str  # FLORES-200 / NLLB / IndicTrans2 code
    name: str
    native: str
    script: str  # ISO 15924 script of the default written form


LANGUAGES: dict[str, Language] = {
    "sa": Language("sa", "san_Deva", "Sanskrit", "संस्कृतम्", "Deva"),
    "hi": Language("hi", "hin_Deva", "Hindi", "हिन्दी", "Deva"),
    "en": Language("en", "eng_Latn", "English", "English", "Latn"),
    "zh": Language("zh", "zho_Hans", "Chinese", "中文", "Hans"),
}

_ALIASES = {
    "san": "sa", "sanskrit": "sa", "san_deva": "sa",
    "hin": "hi", "hindi": "hi", "hin_deva": "hi",
    "eng": "en", "english": "en", "eng_latn": "en",
    "zho": "zh", "chi": "zh", "cmn": "zh", "chinese": "zh", "mandarin": "zh",
    "zho_hans": "zh", "zh-cn": "zh", "zh-hans": "zh", "zh-hant": "zh", "zh-tw": "zh",
}  # fmt: skip


def get_language(code: str) -> Language:
    """Resolve a user-supplied code or alias to a Language, or raise UnknownLanguageError."""
    key = (code or "").strip().lower()
    key = _ALIASES.get(key, key)
    try:
        return LANGUAGES[key]
    except KeyError:
        valid = ", ".join(LANGUAGES)
        raise UnknownLanguageError(f"Unknown language {code!r}. Supported: {valid}.") from None


def all_pairs() -> list[tuple[str, str]]:
    """Every ordered pair of distinct supported languages (12 of them)."""
    return [(a, b) for a in LANGUAGES for b in LANGUAGES if a != b]
