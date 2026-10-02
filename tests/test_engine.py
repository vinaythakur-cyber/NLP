import pytest

from fakes import FakeTranslator, make_backends
from lingua_bridge.config import Settings
from lingua_bridge.engine import LinguaBridge
from lingua_bridge.errors import DetectionError, InputTooLongError, UnknownLanguageError
from lingua_bridge.schemas import ConversionOp, ConvertRequest


def test_translate_returns_route_and_text(engine):
    r = engine.translate("मुझे चाय पसंद है।", src="hi", tgt="en")
    assert (r.via, r.src, r.tgt) == ("direct", "hi", "en")
    assert r.text == "[hi>en:it2] मुझे चाय पसंद है।" and r.route[0].model == "fake/it2"


def test_auto_detect_sets_source_and_reports_detection(engine):
    r = engine.translate("मुझे चाय पसंद है", tgt="en")
    assert r.src == "hi" and r.detected is not None and r.detected.language == "hi"


def test_ambiguous_detection_warns_instead_of_pretending(engine):
    r = engine.translate("नमस्ते", tgt="en")
    assert any("weak" in w for w in r.warnings)


def test_auto_with_undetectable_text_raises(engine):
    with pytest.raises(DetectionError):
        engine.translate("12345", tgt="en")
    with pytest.raises(DetectionError):
        engine.translate("こんにちは", tgt="en")


def test_iast_sanskrit_is_converted_to_devanagari_before_the_model(engine, backends):
    r = engine.translate("rāmaḥ vanaṃ gacchati", src="sa", tgt="en")
    sent = backends["indictrans2"].calls[0][2][0]
    assert sent == "रामः वनं गच्छति"
    assert any("IAST" in w for w in r.warnings)


def test_harvard_kyoto_and_itrans_fallback(engine, backends):
    engine.translate("dharmakSetre kurukSetre samavetA yuyutsavaH", src="sa", tgt="en")
    assert backends["indictrans2"].calls[-1][2][0].startswith("धर्मक्षेत्रे")
    r = engine.translate(
        "rAma vana gacChati", src="sa", tgt="en"
    )  # not detected as HK: assumed ITRANS
    assert any("ITRANS" in w or "HK" in w for w in r.warnings)


def test_hinglish_input_goes_through_the_hinglish_engine(engine, backends):
    r = engine.translate("mera naam Vinay hai", src="hi", tgt="en")
    assert backends["indictrans2"].calls[-1][2][0] == "मेरा नाम विनय है"
    assert any("Hinglish" in w for w in r.warnings)


def test_traditional_chinese_input_is_simplified_for_the_model(engine, backends):
    r = engine.translate("我喜歡喝茶", src="zh", tgt="en")
    assert backends["zh"].calls[-1][2][0] == "我喜欢喝茶"
    assert any("Traditional" in w for w in r.warnings)


def test_chinese_output_is_simplified_by_default_and_traditional_on_request():
    class Zh(FakeTranslator):
        def translate(self, texts, src, tgt):
            return ["我喜欢喝茶。" for _ in texts]

    eng = LinguaBridge(Settings(_env_file=None), make_backends(zh=Zh("zh", zh_only=True)))
    assert eng.translate("I like tea.", src="en", tgt="zh").text == "我喜欢喝茶。"
    assert (
        eng.translate("I like tea.", src="en", tgt="zh", zh_variant="traditional").text
        == "我喜歡喝茶。"
    )


def test_multi_sentence_text_is_split_translated_and_rejoined(engine, backends):
    r = engine.translate("One. Two.\nThree.", src="en", tgt="hi")
    assert backends["indictrans2"].calls[0][2] == ["One.", "Two.", "Three."]
    assert r.text == "[en>hi:it2] One. [en>hi:it2] Two.\n[en>hi:it2] Three."


def test_same_language_is_identity_with_a_note(engine):
    r = engine.translate("hello", src="en", tgt="en")
    assert (
        r.via == "identity" and r.text == "hello" and any("same language" in w for w in r.warnings)
    )


def test_sanskrit_to_chinese_reports_a_pivot(engine):
    r = engine.translate("रामः वनं गच्छति", src="sa", tgt="zh")
    assert r.via == "pivot" and [(h.src, h.tgt) for h in r.route] == [("sa", "en"), ("en", "zh")]


def test_input_limit_and_unknown_language(backends):
    eng = LinguaBridge(Settings(_env_file=None, max_input_chars=10), backends)
    with pytest.raises(InputTooLongError, match="LB_MAX_INPUT_CHARS"):
        eng.translate("x" * 11, src="en", tgt="hi")
    with pytest.raises(UnknownLanguageError):
        eng.translate("x", src="en", tgt="klingon")


def test_nllb_only_setting_routes_everything_to_nllb(backends):
    eng = LinguaBridge(Settings(_env_file=None, translation_engine="nllb"), backends)
    r = eng.translate("रामः वनं गच्छति", src="sa", tgt="zh")
    assert r.via == "direct" and r.route[0].backend == "nllb"


@pytest.mark.parametrize(
    "req,expected,fidelity",
    [
        (
            ConvertRequest(
                text="संस्कृतम्",
                op=ConversionOp.TRANSLITERATE,
                source_scheme="devanagari",
                target_scheme="iast",
            ),
            "saṃskṛtam",
            "lossless",
        ),
        (
            ConvertRequest(text="संस्कृतम्", op=ConversionOp.TRANSLITERATE, target_scheme="roman"),
            "samskritam",
            "lossy",
        ),
        (ConvertRequest(text="mera naam", op=ConversionOp.HINGLISH), "मेरा नाम", "best_effort"),
        (
            ConvertRequest(text="你好", op=ConversionOp.PINYIN, pinyin_style="numbers"),
            "ni3 hao3",
            "lossy",
        ),
        (
            ConvertRequest(
                text="我喜欢茶", op=ConversionOp.CHINESE_SCRIPT, chinese_target="traditional"
            ),
            "我喜歡茶",
            "best_effort",
        ),
        (
            ConvertRequest(
                text="我喜歡茶", op=ConversionOp.CHINESE_SCRIPT, chinese_target="simplified"
            ),
            "我喜欢茶",
            "best_effort",
        ),
    ],
)
def test_conversion_operations_report_fidelity(engine, req, expected, fidelity):
    r = engine.convert(req)
    assert r.text == expected and r.fidelity == fidelity


def test_model_status_lists_every_model(engine):
    keys = {m["key"] for m in engine.model_status()}
    assert {"it2_en_indic", "it2_indic_en", "it2_indic_indic", "nllb"} <= keys
