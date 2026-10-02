"""Script and language detection.

Layer 1 finds the *script* from Unicode ranges (a lookup, never wrong about which block a
character is in). Layer 2 finds the *language* within that script, which is statistics:

* Han            -> Chinese (Simplified vs Traditional by counting script-specific characters)
* Latin          -> IAST or Harvard-Kyoto Sanskrit (via diacritics / mid-word capitals), Hinglish
                    or English (by comparing common-word lists)
* Devanagari     -> Hindi vs Sanskrit. They share a script, so the result is a scored guess with
                    an ``ambiguous`` flag instead of false confidence.

No model downloads: everything here is offline and deterministic.
"""

from __future__ import annotations

import re
import unicodedata

from .convert import chinese as zh_tools
from .convert._hinglish_lexicon import HINGLISH_MARKERS
from .convert.devanagari import Scheme, transliterate
from .errors import DetectionError
from .schemas import Candidate, DetectionResult

# ----------------------------------------------------------------- layer 1: script

_BLOCKS = {
    "Deva": [(0x0900, 0x097F), (0xA8E0, 0xA8FF)],
    "Han": [(0x4E00, 0x9FFF), (0x3400, 0x4DBF), (0xF900, 0xFAFF), (0x20000, 0x2A6DF)],
    "Kana": [(0x3040, 0x30FF)],
}


def _block_of(ch: str) -> str | None:
    cp = ord(ch)
    for name, ranges in _BLOCKS.items():
        if any(lo <= cp <= hi for lo, hi in ranges):
            return name
    if ch.isalpha() and unicodedata.name(ch, "").startswith("LATIN"):
        return "Latn"
    return None


def script_shares(text: str) -> dict[str, float]:
    """Share of script-bearing characters per script (Deva, Han, Kana, Latn)."""
    counts: dict[str, int] = {}
    for ch in text:
        b = _block_of(ch)
        if b:
            counts[b] = counts.get(b, 0) + 1
    total = sum(counts.values())
    return {k: v / total for k, v in counts.items()} if total else {}


# ----------------------------------------------------- layer 2a: Devanagari hi vs sa

_HINDI_WORDS = set(
    "है हैं था थे थी में का की के को से पर और नहीं यह वह ये वे कि तो भी एक हो गया गई गए कर करना "
    "रहा रहे रही लिए साथ बहुत जो क्या कैसे मैं मुझे हम तुम आप अपना मेरा मेरी मेरे तेरा उस इस यहाँ वहाँ "
    "कब कहाँ क्यों लेकिन अगर या ही सकता सकती होता होती चाहिए वाला वाली हूँ कौन कुछ सब बहुत अब "
    "जब तब फिर अभी कल आज उसने उन्होंने मैंने हमने तुमने किया दिया लिया होगा होगी जाएगा जाता जाती "
    "करता करती करते कहा कहते थीं रहता पास तक भर बाद पहले".split()
)  # fmt: skip
_SANSKRIT_WORDS = set(
    "च अपि एव इति खलु अथ तत् यत् एवम् तदा यदा किम् अहम् त्वम् सः तत्र अत्र इदम् एषः मम तव अस्ति "
    "सन्ति भवति गच्छति इत्यादि तथा यथा कः का कदा कुत्र कथम् नमः स्वस्ति धर्मः कर्म धर्मक्षेत्रे "
    "कुरुक्षेत्रे समवेताः उवाच श्रीभगवानुवाच वनम् गृहम् रामः कृष्णः अहं त्वं नास्ति भवान् भवती "
    "पुनः अतः तस्मात् तस्य तेषाम् एतत् तेन तस्मै अस्य अस्मिन् यस्य येन सर्वम् सर्वे सर्वः".split()
)  # fmt: skip
_SA_VERB_ENDINGS = ("ति", "न्ति", "सि", "मि", "ते", "न्ते", "ामि", "ाम", "थ", "त्")
_WORD_SPLIT = re.compile(r"[\s।॥,.;:!?\"'()\-–—]+")


def _classify_devanagari(text: str) -> tuple[float, float, int]:
    """Return (p_sanskrit, p_hindi, evidence) from lexical and morphological cues."""
    tokens = [t for t in _WORD_SPLIT.split(text) if t]
    sa = hi = 0.0
    for t in tokens:
        if t in _HINDI_WORDS:
            hi += 2.5
        if t in _SANSKRIT_WORDS:
            sa += 2.0
        if t.endswith("ः"):  # visarga: very rare in Hindi
            sa += 2.0
        if t.endswith("म्") and len(t) > 2:  # final -m with virama: wanam, griham...
            sa += 1.5
        if len(t) > 3 and t.endswith(_SA_VERB_ENDINGS[:6]) and t not in _HINDI_WORDS:
            sa += 0.8
        if "ँ" in t:  # chandrabindu is common in Hindi
            hi += 1.0
        if "़" in t:  # nukta marks Perso-Arabic/English loans, absent in Sanskrit
            hi += 1.0
    evidence = int(sa + hi)
    p_sa = (sa + 0.5) / (sa + hi + 1.0)
    return p_sa, 1.0 - p_sa, evidence


# ------------------------------------------------------ layer 2b: Latin sub-classes

_IAST_CHARS = set("āīūṛṝḷḹṃṁḥśṣṭḍṇṅñĀĪŪṚṜḶṂḤŚṢṬḌṆ")
_HK_TOKEN = re.compile(r"\b[a-z]*[a-z][AIURMHTDNSGJzL][A-Za-z]*\b")
_EN_STOP = set(
    "the a an and of to in is are was were be been i you he she it we they this that with for on "
    "at by from as not have has had will would can could my your his her our their what who how "
    "why when where which there here very good time people just like love hello thanks please "
    "am do does did if or but so than then about into out up down over".split()
)  # fmt: skip


def _latin_language(
    text: str,
) -> tuple[str | None, list[Candidate], float, bool, str | None, str | None]:
    """-> (language, candidates, confidence, ambiguous, latin_scheme, note)"""
    chars = {c for c in text if c.isalpha()}
    tokens = re.findall(r"[A-Za-zĀ-ſḀ-ỿ']+", text)
    if chars & _IAST_CHARS:
        deva = transliterate(text, Scheme.IAST, Scheme.DEVANAGARI)
        lang, cands, conf, amb, _, _ = _devanagari_language(deva)
        return lang, cands, conf, amb, "iast", "Romanized Sanskrit/Hindi with IAST diacritics."
    hk_hits = [
        t for t in tokens if _HK_TOKEN.fullmatch(t) and t != t.capitalize() and t != t.upper()
    ]
    if tokens and len(hk_hits) >= 2 and len(hk_hits) / len(tokens) >= 0.25:
        deva = transliterate(text, Scheme.HK, Scheme.DEVANAGARI)
        lang, cands, conf, amb, _, _ = _devanagari_language(deva)
        return (
            lang,
            cands,
            conf,
            amb,
            "hk",
            "Looks like Harvard-Kyoto Sanskrit (mid-word capitals).",
        )
    low = [t.lower() for t in tokens]
    n = max(len(low), 1)
    h = sum(t in HINGLISH_MARKERS for t in low) / n
    e = sum(t in _EN_STOP for t in low) / n
    if h == 0 and e == 0:
        cands = [Candidate(language="en", score=0.6), Candidate(language="hi", score=0.4)]
        return (
            "en",
            cands,
            0.6,
            True,
            "plain",
            "No known English or Hinglish function words; guessing English.",
        )
    p_hi = (h + 0.02) / (h + e + 0.04)
    cands = sorted(
        [
            Candidate(language="hi", score=round(p_hi, 3)),
            Candidate(language="en", score=round(1 - p_hi, 3)),
        ],
        key=lambda c: -c.score,
    )
    top = cands[0]
    scheme = "hinglish" if top.language == "hi" else "plain"
    note = "Roman Hindi (Hinglish)." if scheme == "hinglish" else None
    return top.language, cands, top.score, top.score < 0.7, scheme, note


def _devanagari_language(
    text: str,
) -> tuple[str | None, list[Candidate], float, bool, None, str | None]:
    p_sa, p_hi, evidence = _classify_devanagari(text)
    cands = sorted(
        [
            Candidate(language="sa", score=round(p_sa, 3)),
            Candidate(language="hi", score=round(p_hi, 3)),
        ],
        key=lambda c: -c.score,
    )
    top = cands[0]
    ambiguous = top.score < 0.7
    note = None
    if evidence == 0:
        top = Candidate(language="hi", score=0.5)
        cands = [top, Candidate(language="sa", score=0.5)]
        note = "No Hindi or Sanskrit markers found (very short text?); defaulting to Hindi."
        ambiguous = True
    elif ambiguous:
        note = "Hindi and Sanskrit share Devanagari; the evidence is too close to call."
    return top.language, cands, top.score, ambiguous, None, note


# --------------------------------------------------------------------- public API


def detect(text: str) -> DetectionResult:
    """Detect script and language. Raises DetectionError for empty or script-less input."""
    if not text or not text.strip():
        raise DetectionError("Cannot detect the language of empty text.")
    shares = script_shares(text)
    if not shares:
        raise DetectionError("No letters found in the text (only digits or symbols).")
    dominant, share = max(shares.items(), key=lambda kv: kv[1])
    mixed = share < 0.7

    if dominant == "Kana":
        return DetectionResult(
            script="Kana", language=None, confidence=0.0, ambiguous=False,
            note="Japanese kana detected; Japanese is not supported.",
        )  # fmt: skip

    if dominant == "Han":
        simp, trad = zh_tools.script_counts(text)
        if simp > trad:
            script = "Hans"
        elif trad > simp:
            script = "Hant"
        else:
            script = "Han"
        conf = 0.6 if mixed else 0.97
        note = (
            "Simplified/Traditional cannot be told apart (only shared characters)."
            if script == "Han"
            else None
        )
        return DetectionResult(
            script=script, language="zh", confidence=conf, ambiguous=mixed,
            candidates=[Candidate(language="zh", score=conf)], note=note,
        )  # fmt: skip

    if dominant == "Deva":
        lang, cands, conf, amb, scheme, note = _devanagari_language(text)
        script = "Deva"
    else:
        lang, cands, conf, amb, scheme, note = _latin_language(text)
        script = "Latn"
    if mixed:
        conf = round(conf * 0.8, 3)
        amb = True
        note = ((note + " ") if note else "") + "Text mixes several scripts."
    return DetectionResult(
        script="Mixed" if mixed and share < 0.5 else script,
        language=lang, confidence=round(conf, 3), ambiguous=amb, candidates=cands,
        latin_scheme=scheme, note=note,
    )  # fmt: skip
