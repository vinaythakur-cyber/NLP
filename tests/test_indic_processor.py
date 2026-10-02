"""The pure-Python IndicProcessor port must match the compiled original, sentence for sentence."""

import json
from pathlib import Path

import pytest

pytest.importorskip("regex")
pytest.importorskip("sacremoses")
pytest.importorskip("indicnlp")

from lingua_bridge.translate._indic_processor import IndicProcessor  # noqa: E402

GOLDEN = json.loads(
    Path(__file__).with_name("data").joinpath("indic_processor_golden.json").read_text("utf8")
)


@pytest.mark.parametrize("case", GOLDEN["pre"], ids=lambda c: f"{c['src']}->{c['tgt']}")
def test_preprocess_matches_compiled_original(case):
    ip = IndicProcessor(inference=True)
    assert (
        ip.preprocess_batch(case["in"], src_lang=case["src"], tgt_lang=case["tgt"]) == case["out"]
    )


@pytest.mark.parametrize("case", GOLDEN["post"], ids=lambda c: c["lang"])
def test_postprocess_matches_compiled_original(case):
    ip = IndicProcessor(inference=True)
    ip.preprocess_batch(case["pre_in"], src_lang="eng_Latn", tgt_lang=case["lang"])
    assert ip.postprocess_batch(case["in"], lang=case["lang"]) == case["out"]


def test_placeholders_round_trip():
    ip = IndicProcessor(inference=True)
    pre = ip.preprocess_batch(["Mail me at someone@example.com today."], "eng_Latn", "hin_Deva")
    assert "someone@example.com" not in pre[0]
    assert ip.postprocess_batch(["कृपया <ID1> पर लिखें"], lang="hin_Deva") == [
        "कृपया someone@example.com पर लिखें"
    ]
