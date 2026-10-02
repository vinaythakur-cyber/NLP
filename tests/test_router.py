import logging

import pytest

from fakes import FakeTranslator, make_backends
from lingua_bridge.errors import ModelAccessError, ModelUnavailableError, UnsupportedPairError
from lingua_bridge.languages import all_pairs
from lingua_bridge.translate.router import Router


def test_sa_hi_en_pairs_are_direct_indictrans2(backends):
    r = Router(backends)
    for a, b in [
        ("sa", "hi"),
        ("hi", "sa"),
        ("sa", "en"),
        ("en", "sa"),
        ("hi", "en"),
        ("en", "hi"),
    ]:
        res = r.translate(["x"], a, b)
        assert res.via == "direct" and [h.backend for h in res.hops] == ["indictrans2"]


def test_chinese_pairs_with_english_and_hindi_are_direct(backends):
    r = Router(backends)
    for a, b in [("en", "zh"), ("zh", "en"), ("hi", "zh"), ("zh", "hi")]:
        res = r.translate(["x"], a, b)
        assert res.via == "direct" and res.hops[0].backend == "zh"


def test_sanskrit_chinese_pivots_through_english_in_order(backends, caplog):
    r = Router(backends)
    with caplog.at_level(logging.INFO, logger="lingua_bridge.route"):
        res = r.translate(["text"], "sa", "zh")
    assert res.via == "pivot"
    assert [(h.src, h.tgt, h.backend) for h in res.hops] == [
        ("sa", "en", "indictrans2"),
        ("en", "zh", "zh"),
    ]
    assert res.texts == ["[en>zh:zh] [sa>en:it2] text"]  # hop 2 consumed hop 1's output
    line = next(rec.message for rec in caplog.records if rec.name == "lingua_bridge.route")
    assert "via=pivot" in line and "PIVOT through English" in line and "sa->en" in line


def test_every_one_of_twelve_pairs_has_a_route(backends):
    r = Router(backends)
    for a, b in all_pairs():
        assert r.plan(a, b), f"no route for {a}->{b}"


def test_direct_route_is_logged_without_pivot_warning(backends, caplog):
    with caplog.at_level(logging.INFO, logger="lingua_bridge.route"):
        Router(backends).translate(["x"], "hi", "en")
    line = next(rec.message for rec in caplog.records if rec.name == "lingua_bridge.route")
    assert "via=direct" in line and "PIVOT" not in line


def test_identity_does_not_call_any_model(backends):
    res = Router(backends).translate(["x"], "hi", "hi")
    assert res.via == "identity" and res.hops == [] and res.texts == ["x"]
    assert not any(b.calls for b in backends.values())


def test_override_direct_for_sanskrit_chinese(backends):
    res = Router(backends, {"sa>zh": "direct"}).translate(["x"], "sa", "zh")
    assert res.via == "direct" and res.hops[0].backend == "zh"


def test_override_to_force_a_backend_and_to_force_a_pivot(backends):
    assert (
        Router(backends, {"hi>en": "nllb"}).translate(["x"], "hi", "en").hops[0].backend == "nllb"
    )
    res = Router(backends, {"hi>zh": "pivot"}).translate(["x"], "hi", "zh")
    assert res.via == "pivot" and len(res.hops) == 2


def test_bad_overrides_fail_clearly(backends):
    with pytest.raises(UnsupportedPairError):
        Router(backends, {"hi>en": "nonexistent"}).plan("hi", "en")
    with pytest.raises(UnsupportedPairError):
        Router(backends, {"en>zh": "pivot"}).plan(
            "en", "zh"
        )  # cannot pivot a pair that includes English


def test_no_backend_for_pair_is_an_error():
    r = Router({"indictrans2": FakeTranslator("it2", {("hi", "en")})})
    with pytest.raises(UnsupportedPairError, match="hi->sa"):
        r.plan("hi", "sa")


def test_nllb_only_mode_has_no_pivot_and_no_indictrans2(backends):
    r = Router(backends, preference=("nllb",), pivot_by_default=False)
    res = r.translate(["x"], "sa", "zh")
    assert res.via == "direct" and res.hops[0].backend == "nllb"
    assert backends["indictrans2"].calls == []


def test_segment_count_and_order_are_preserved(backends):
    res = Router(backends).translate(["a", "b", "c"], "hi", "en")
    assert res.texts == ["[hi>en:it2] a", "[hi>en:it2] b", "[hi>en:it2] c"]
    assert res.hops[0].segments == 3 and res.hops[0].model == "fake/it2"


def test_gated_indictrans2_falls_back_to_nllb_with_a_warning():
    backends = make_backends(indictrans2=FakeTranslator("it2", error=ModelAccessError("gated")))
    res = Router(backends).translate(["x"], "sa", "en")
    assert res.hops[0].backend == "nllb" and res.texts == ["[sa>en:nllb] x"]
    assert len(res.warnings) == 1 and "lingua login" in res.warnings[0]


def test_fallback_can_be_disabled():
    backends = make_backends(indictrans2=FakeTranslator("it2", error=ModelAccessError("gated")))
    with pytest.raises(ModelAccessError):
        Router(backends, fallback_to_nllb=False).translate(["x"], "sa", "en")


def test_only_access_errors_trigger_fallback():
    backends = make_backends(
        indictrans2=FakeTranslator("it2", error=ModelUnavailableError("out of memory"))
    )
    with pytest.raises(ModelUnavailableError, match="out of memory"):
        Router(backends).translate(["x"], "sa", "en")
