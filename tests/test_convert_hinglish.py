import pytest

from lingua_bridge.convert import hinglish
from lingua_bridge.convert.hinglish import RuleBasedBackend, get_backend
from lingua_bridge.errors import ConversionError


@pytest.fixture(autouse=True)
def _clear_cache():
    hinglish._cache.clear()
    yield
    hinglish._cache.clear()


@pytest.mark.parametrize(
    "roman,deva",
    [
        ("mera naam Vinay hai", "मेरा नाम विनय है"),
        ("mujhe chai pasand hai", "मुझे चाय पसंद है"),
        ("aap kaise ho?", "आप कैसे हो?"),
        ("kal school nahi jaana", "कल स्कूल नहीं जाना"),
        ("main kal Delhi jaunga", "मैं कल दिल्ली जाऊँगा"),
    ],
)
def test_common_sentences(roman, deva):
    assert RuleBasedBackend().convert(roman) == deva


def test_unknown_words_use_rules_and_drop_the_final_virama():
    out = RuleBasedBackend().convert("Vinay")
    assert out == "विनय" and not out.endswith("्")


def test_digits_punctuation_and_existing_devanagari_pass_through():
    assert RuleBasedBackend().convert("hai 123, ok!").startswith("है 123,")
    assert RuleBasedBackend().convert("नमस्ते hai") == "नमस्ते है"


def test_spelling_variants_map_to_one_word():
    b = RuleBasedBackend()
    assert b.convert("kaise") == b.convert("kese") == "कैसे"


def test_auto_falls_back_to_rule_when_ai4bharat_is_missing():
    assert get_backend("auto").name == "rule"


def test_explicit_ai4bharat_fails_clearly_when_missing():
    with pytest.raises(ConversionError, match="LB_HINGLISH_BACKEND=rule"):
        get_backend("ai4bharat")


def test_unknown_backend_rejected():
    with pytest.raises(ConversionError):
        get_backend("magic")
