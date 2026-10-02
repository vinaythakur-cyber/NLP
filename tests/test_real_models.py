"""End-to-end with real weights. Slow (downloads GBs) and skipped by default:

    LB_RUN_SLOW=1 pytest -m slow

IndicTrans2 tests need a Hugging Face login with accepted terms; they skip otherwise.
"""

import os
import re

import pytest

from lingua_bridge.config import Settings
from lingua_bridge.engine import LinguaBridge

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        not os.environ.get("LB_RUN_SLOW"), reason="set LB_RUN_SLOW=1 to run real-model tests"
    ),
]
pytest.importorskip("torch")
pytest.importorskip("transformers")

DEVANAGARI = re.compile(r"[ऀ-ॿ]")
HAN = re.compile(r"[一-鿿]")


@pytest.fixture(scope="module")
def real():
    return LinguaBridge(Settings(_env_file=None, fallback_to_nllb=False))


def test_nllb_english_to_chinese():
    eng = LinguaBridge(Settings(_env_file=None, translation_engine="nllb"))
    r = eng.translate("I like tea.", src="en", tgt="zh")
    assert HAN.search(r.text)


def test_indictrans2_english_to_hindi(real):
    assert DEVANAGARI.search(real.translate("I like tea.", src="en", tgt="hi").text)


def test_indictrans2_sanskrit_to_english(real):
    out = real.translate("रामः वनं गच्छति।", src="sa", tgt="en").text
    assert re.search(r"[A-Za-z]{3}", out)


def test_sanskrit_to_chinese_pivots(real):
    r = real.translate("रामः वनं गच्छति।", src="sa", tgt="zh")
    assert r.via == "pivot" and HAN.search(r.text)
