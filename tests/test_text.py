from lingua_bridge.translate._text import join_text, split_text


def roundtrip(text, tgt="en"):
    segs, layout = split_text(text)
    return segs, join_text(segs, layout, tgt)


def test_splits_sentences_and_rejoins():
    segs, out = roundtrip("Hello there. How are you? Fine!")
    assert segs == ["Hello there.", "How are you?", "Fine!"]
    assert out == "Hello there. How are you? Fine!"


def test_danda_is_a_sentence_boundary():
    segs, _ = roundtrip("राम वन जाता है। सीता घर जाती है।")
    assert segs == ["राम वन जाता है।", "सीता घर जाती है।"]


def test_newlines_survive():
    segs, out = roundtrip("Line one.\n\nLine two.")
    assert segs == ["Line one.", "Line two."]
    assert out == "Line one.\n\nLine two."


def test_chinese_target_joins_without_spaces():
    segs, layout = split_text("First. Second.")
    assert join_text(["你好。", "再见。"], layout, "zh") == "你好。再见。"


def test_chinese_source_splits_on_fullwidth_enders():
    segs, _ = roundtrip("我喜欢茶。你呢？好！")
    assert segs == ["我喜欢茶。", "你呢？", "好！"]


def test_long_segments_are_chunked_under_the_limit():
    text = " ".join(["word"] * 400)  # 1999 characters, one sentence
    segs, out = roundtrip(text)
    assert len(segs) > 1 and all(len(s) <= 400 for s in segs)
    assert out.split() == text.split()


def test_empty_text_has_no_segments():
    assert split_text("   ") == ([], [])
