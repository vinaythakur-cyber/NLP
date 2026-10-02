import pytest

from lingua_bridge.convert.chinese import (
    ChineseVariant,
    PinyinStyle,
    script_counts,
    to_pinyin,
    to_simplified,
    to_traditional,
)


def test_pinyin_styles():
    assert to_pinyin("你好", PinyinStyle.MARKS) == "nǐ hǎo"
    assert to_pinyin("你好", "numbers") == "ni3 hao3"
    assert to_pinyin("你好", "plain") == "ni hao"


def test_pinyin_polyphones_use_context():
    assert to_pinyin("银行", "numbers") == "yin2 hang2"
    assert to_pinyin("行长", "numbers") == "hang2 zhang3"


def test_pinyin_punctuation_attaches_and_other_text_passes_through():
    assert to_pinyin("你好，世界。") == "nǐ hǎo, shì jiè."
    assert "hello" in to_pinyin("你好 hello")


def test_simplified_to_traditional_and_back():
    assert to_traditional("我喜欢喝茶") == "我喜歡喝茶"
    assert to_simplified("我喜歡喝茶") == "我喜欢喝茶"


def test_regional_variants_differ_on_vocabulary():
    assert to_traditional("软件", ChineseVariant.STANDARD) == "軟件"
    assert to_traditional("软件", ChineseVariant.TAIWAN) == "軟體"
    assert to_simplified("軟體", "taiwan") == "软件"


def test_round_trip_is_not_guaranteed_by_design():
    # 后 (queen / after) and 發/髮 merged into 发 when simplified, so the reverse is a choice.
    assert to_traditional(to_simplified("頭髮")) != "頭髮" or to_traditional("发") in ("發", "髮")


def test_script_counts():
    assert script_counts("我喜欢喝茶")[0] > 0
    assert script_counts("我喜歡喝茶")[1] > 0
    assert script_counts("你好") == (0, 0)


def test_unknown_style_rejected():
    with pytest.raises(ValueError):
        to_pinyin("你好", "klingon")
