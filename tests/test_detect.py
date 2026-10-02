import pytest

from lingua_bridge.detect import detect, script_shares
from lingua_bridge.errors import DetectionError


@pytest.mark.parametrize(
    "text,script,lang",
    [
        ("मुझे चाय पसंद है", "Deva", "hi"),
        ("वह कल दिल्ली जाएगा।", "Deva", "hi"),
        ("धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः", "Deva", "sa"),
        ("रामः वनं गच्छति", "Deva", "sa"),
        ("I like tea very much", "Latn", "en"),
        ("The quick brown fox", "Latn", "en"),
        ("mera naam Vinay hai", "Latn", "hi"),
        ("tum kya kar rahe ho", "Latn", "hi"),
        ("我喜欢喝茶", "Hans", "zh"),
        ("我喜歡喝茶", "Hant", "zh"),
    ],
)
def test_script_and_language(text, script, lang):
    r = detect(text)
    assert (r.script, r.language) == (script, lang)
    assert not r.ambiguous


def test_romanized_sanskrit_schemes():
    iast = detect("dharmakṣetre kurukṣetre samavetā yuyutsavaḥ")
    hk = detect("dharmakSetre kurukSetre samavetA yuyutsavaH")
    assert (iast.language, iast.latin_scheme) == ("sa", "iast")
    assert (hk.language, hk.latin_scheme) == ("sa", "hk")


def test_hinglish_is_reported_as_hindi_with_latin_scheme():
    r = detect("aap kaise ho")
    assert (r.language, r.latin_scheme) == ("hi", "hinglish")


def test_hindi_sanskrit_ambiguity_is_flagged_not_hidden():
    r = detect("नमस्ते")  # no distinguishing marker either way
    assert r.ambiguous and r.confidence <= 0.6
    assert {c.language for c in r.candidates} == {"hi", "sa"}


def test_han_without_script_specific_characters_is_ambiguous_script():
    assert detect("你好").script == "Han"


def test_japanese_kana_is_not_claimed_as_chinese():
    r = detect("こんにちは")
    assert r.language is None and r.script == "Kana"


def test_genuinely_mixed_scripts_are_flagged():
    r = detect("hello world चाय पसंद")  # roughly half Latin, half Devanagari
    assert r.ambiguous and "mixes" in (r.note or "")


def test_mostly_one_script_is_not_called_mixed():
    assert "mixes" not in (detect("मुझे tea पसंद है").note or "")


@pytest.mark.parametrize("bad", ["", "   ", "12345 !!!"])
def test_no_letters_raises(bad):
    with pytest.raises(DetectionError):
        detect(bad)


def test_script_shares_sum_to_one():
    shares = script_shares("hello मुझे")
    assert abs(sum(shares.values()) - 1) < 1e-9 and set(shares) == {"Latn", "Deva"}
