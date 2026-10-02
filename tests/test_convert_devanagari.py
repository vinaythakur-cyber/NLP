"""Lossless round-trips where the scheme allows it, and an explicit list of where it does not."""

import itertools
import unicodedata

import pytest

from lingua_bridge.convert.devanagari import Scheme, fidelity_for, parse_scheme, transliterate
from lingua_bridge.errors import ConversionError

LOSSLESS = ["devanagari", "iast", "hk", "itrans"]

# Well-formed Sanskrit and Hindi: vowels, consonants, conjuncts, signs, digits, danda, Om.
CORPUS = [
    "धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः",
    "मामकाः पाण्डवाश्चैव किमकुर्वत सञ्जय ॥",
    "संस्कृतम् ॐ",
    "अ आ इ ई उ ऊ ऋ ॠ ऌ ए ऐ ओ औ अं अः",
    "क ख ग घ ङ च छ ज झ ञ ट ठ ड ढ ण त थ द ध न प फ ब भ म य र ल व श ष स ह ळ क्ष ज्ञ",
    "गृहं ऋषिः कृष्णः श्रीमद्भगवद्गीता",
    "सत्यमेव जयते । १२३४५६७८९०",
    "मुझे चाय पसंद है।",
    "ज्ञानं परमं ध्येयम्",
]


def nfd(s: str) -> str:
    return unicodedata.normalize("NFD", s)


@pytest.mark.parametrize("scheme", ["iast", "hk", "itrans"])
@pytest.mark.parametrize("text", CORPUS)
def test_devanagari_round_trip_is_lossless(text, scheme):
    there = transliterate(text, "devanagari", scheme)
    assert nfd(transliterate(there, scheme, "devanagari")) == nfd(text)


@pytest.mark.parametrize("a,b", list(itertools.permutations(LOSSLESS, 2)))
def test_every_pair_of_lossless_schemes_composes_to_identity(a, b):
    deva = CORPUS[0] + " " + CORPUS[5]
    start = transliterate(deva, "devanagari", a)
    via = transliterate(start, a, b)
    assert transliterate(via, b, a) == start


def test_known_values():
    assert transliterate("संस्कृतम्", "devanagari", "iast") == "saṃskṛtam"
    assert transliterate("संस्कृतम्", "devanagari", "hk") == "saMskRtam"
    assert transliterate("rAmaH", "hk", "devanagari") == "रामः"
    assert transliterate("rāmaḥ", "iast", "devanagari") == "रामः"


def test_documented_exceptions_are_real():
    """Contract boundary: ill-formed or ambiguous sequences do not round-trip."""
    # A consonant followed by an independent vowel is a hiatus, but IAST 'kai' reads as क + ऐ.
    assert transliterate(transliterate("कइ", "devanagari", "iast"), "iast", "devanagari") != "कइ"
    # A dependent vowel sign with no consonant is not valid text.
    assert transliterate(transliterate("ा", "devanagari", "iast"), "iast", "devanagari") == "आ"


def test_casual_roman_is_lossy_and_one_way():
    roman = transliterate("संस्कृतम् ऋषिः", "devanagari", "roman")
    assert roman == "samskritam rishih"
    assert all(ord(c) < 128 for c in roman)
    assert fidelity_for(Scheme.DEVANAGARI, Scheme.ROMAN) == "lossy"


def test_roman_input_goes_through_the_hinglish_engine():
    assert transliterate("mera naam", "roman", "devanagari") == "मेरा नाम"


def test_fidelity_labels():
    assert fidelity_for(Scheme.DEVANAGARI, Scheme.IAST) == "lossless"
    assert fidelity_for(Scheme.HK, Scheme.ITRANS) == "lossless"
    assert fidelity_for(Scheme.ROMAN, Scheme.DEVANAGARI) == "best_effort"
    assert fidelity_for(Scheme.IAST, Scheme.IAST) == "lossless"


def test_scheme_parsing_accepts_aliases_and_rejects_unknown():
    assert parse_scheme("Harvard-Kyoto") is Scheme.HK
    assert parse_scheme("DEVA") is Scheme.DEVANAGARI
    with pytest.raises(ConversionError, match="Valid schemes"):
        parse_scheme("klingon")


def test_same_scheme_is_a_noop():
    assert transliterate("anything", "iast", "iast") == "anything"
