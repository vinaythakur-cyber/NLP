"""Backend plumbing tests that need torch. They use a tiny randomly initialised model built on the
fly, so they check our code (batching, language tags, decoding), not translation quality."""

import pytest

from lingua_bridge.translate.base import ModelCache


def test_model_cache_evicts_least_recently_used():
    cache = ModelCache(max_loaded=2)
    for key in ("a", "b"):
        cache.get(key, lambda k=key: object())
    cache.get("a", lambda: object())  # touch a so b is the oldest
    cache.get("c", lambda: object())
    assert cache.loaded() == ["a", "c"]


torch = pytest.importorskip("torch")
transformers = pytest.importorskip("transformers")
spm = pytest.importorskip("sentencepiece")


@pytest.fixture(scope="module")
def tiny(tmp_path_factory):
    d = tmp_path_factory.mktemp("tiny")
    corpus = d / "corpus.txt"
    corpus.write_text("\n".join(["hello world this is a test", "namaste duniya", "i like tea very much",
                                 "मुझे चाय पसंद है", "我喜欢喝茶", "the quick brown fox"] * 20), encoding="utf8")  # fmt: skip
    spm.SentencePieceTrainer.train(input=str(corpus), model_prefix=str(d / "sp"), vocab_size=80,
                                   character_coverage=1.0, model_type="unigram", hard_vocab_limit=False)  # fmt: skip
    tok = transformers.NllbTokenizer(vocab_file=str(d / "sp.model"))
    cfg = transformers.M2M100Config(vocab_size=len(tok), d_model=16, encoder_layers=1, decoder_layers=1,
                                    encoder_attention_heads=2, decoder_attention_heads=2, encoder_ffn_dim=32,
                                    decoder_ffn_dim=32, max_position_embeddings=64, pad_token_id=tok.pad_token_id,
                                    bos_token_id=tok.bos_token_id, eos_token_id=tok.eos_token_id,
                                    decoder_start_token_id=tok.eos_token_id)  # fmt: skip
    torch.manual_seed(0)
    return tok, transformers.M2M100ForConditionalGeneration(cfg).eval()


def test_nllb_backend_sets_language_tags_and_preserves_order(tiny, monkeypatch, settings):
    from lingua_bridge.translate.nllb import NllbTranslator

    tok, model = tiny
    captured = {}
    real_generate = model.generate

    def spy(*a, **kw):
        captured["forced_bos"] = kw.get("forced_bos_token_id")
        captured["input_ids"] = kw["input_ids"].clone()
        return real_generate(*a, **kw)

    monkeypatch.setattr(model, "generate", spy)
    monkeypatch.setattr(transformers.AutoTokenizer, "from_pretrained", lambda *a, **k: tok)
    monkeypatch.setattr(
        transformers.AutoModelForSeq2SeqLM, "from_pretrained", lambda *a, **k: model
    )

    s = settings.model_copy(
        update={"device": "cpu", "max_new_tokens": 8, "num_beams": 1, "batch_size": 2}
    )
    t = NllbTranslator(s, ModelCache(2))
    texts = ["hello world", "i like tea very much", "a", "the quick brown fox"]
    out = t.translate(texts, "en", "hi")
    assert len(out) == 4 and all(isinstance(x, str) for x in out)
    assert captured["forced_bos"] == tok.convert_tokens_to_ids("hin_Deva")
    assert tok.src_lang == "eng_Latn"
    assert captured["input_ids"][0][0].item() == tok.convert_tokens_to_ids(
        "eng_Latn"
    )  # source language tag first
    # the same call twice is deterministic, i.e. outputs map back to inputs in the original order
    assert t.translate(texts, "en", "hi") == out


def test_zh_backend_only_supports_chinese_pairs(settings):
    from lingua_bridge.translate.zh import ChineseTranslator

    z = ChineseTranslator(settings, ModelCache(1))
    assert z.supports("en", "zh") and z.supports("zh", "sa") and not z.supports("sa", "hi")


def test_safe_generate_retries_without_cache_and_in_float32():
    from lingua_bridge.translate.base import safe_generate

    class Cacheless(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.w = torch.nn.Parameter(torch.zeros(1))
            self.calls = []

        def generate(self, **kw):
            self.calls.append(kw.get("use_cache"))
            if kw.get("use_cache"):
                raise AttributeError("'tuple' object has no attribute 'get_seq_length'")
            return "ok"

    m = Cacheless()
    assert safe_generate(m, {}, use_cache=True) == "ok" and m.calls == [True, False]

    class Overflow(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.w = torch.nn.Parameter(torch.zeros(1, dtype=torch.float16))
            self.n = 0

        def generate(self, **kw):
            self.n += 1
            if self.w.dtype != torch.float32:
                raise RuntimeError("probability tensor contains either `inf`, `nan` or element < 0")
            return "fp32-ok"

    o = Overflow()
    assert safe_generate(o, {}) == "fp32-ok" and o.w.dtype == torch.float32 and o.n == 2


def _patch_loaders(monkeypatch, tok, model):
    monkeypatch.setattr(transformers.AutoTokenizer, "from_pretrained", lambda *a, **k: tok)
    monkeypatch.setattr(
        transformers.AutoModelForSeq2SeqLM, "from_pretrained", lambda *a, **k: model
    )


def _indic(settings, **update):
    from lingua_bridge.translate.indic import IndicTranslator

    s = settings.model_copy(
        update={"device": "cpu", "max_new_tokens": 8, "num_beams": 1, "batch_size": 2, **update}
    )
    return IndicTranslator(s, ModelCache(2))


def test_indictrans2_backend_pipeline_with_a_stand_in_model(tiny, monkeypatch, settings):
    """Runs the real IndicTrans2 code path (processor tags, length-sorted batches, decode, postprocess)
    with a tiny stand-in model. It checks orchestration only, not translation quality."""
    tok, model = tiny
    seen = []
    real_tok_call = type(tok).__call__

    def spy(self, text, *a, **k):
        seen.append(list(text))
        return real_tok_call(self, text, *a, **k)

    monkeypatch.setattr(type(tok), "__call__", spy)
    _patch_loaders(monkeypatch, tok, model)
    t = _indic(settings)
    texts = ["hello", "i like tea very much", "a", "the quick brown fox", "namaste duniya"]
    out = t.translate(texts, "en", "hi")
    assert len(out) == 5 and all(isinstance(x, str) for x in out)
    # every sentence reached the tokenizer prefixed with the source and target language tags
    assert all(s.startswith("eng_Latn hin_Deva ") for batch in seen for s in batch)
    assert sum(len(b) for b in seen) == 5 and len(seen) == 3  # batch_size 2 over 5 sentences
    assert t.translate(texts, "en", "hi") == out  # deterministic and order-preserving


def test_indictrans2_model_choice_per_direction(settings):
    from lingua_bridge.translate.indic import IndicTranslator

    t = IndicTranslator(settings, ModelCache(1))
    assert t.model_id("en", "hi").endswith("en-indic-dist-200M")
    assert t.model_id("sa", "en").endswith("indic-en-dist-200M")
    assert t.model_id("sa", "hi").endswith("indic-indic-dist-320M")
    assert t.supports("sa", "hi") and not t.supports("hi", "zh") and not t.supports("en", "en")


def test_failed_generation_does_not_corrupt_the_next_call(tiny, monkeypatch, settings):
    """Regression: placeholders (emails, URLs) must survive a failed call in between."""
    tok, model = tiny
    _patch_loaders(monkeypatch, tok, model)
    t = _indic(settings, batch_size=8)
    real_generate = model.generate
    state = {"fail": True}

    def flaky(*a, **kw):
        if state["fail"]:
            state["fail"] = False
            raise RuntimeError("boom")
        return real_generate(*a, **kw)

    monkeypatch.setattr(model, "generate", flaky)
    with pytest.raises(RuntimeError, match="boom"):
        t.translate(["write to first@example.com now"], "en", "hi")
    ip = t._new_processor()
    pre = ip.preprocess_batch(["write to second@example.com now"], "eng_Latn", "hin_Deva")
    assert "second@example.com" not in pre[0]
    assert ip.postprocess_batch(["<ID1>"], lang="hin_Deva") == ["second@example.com"]
    assert (
        len(t.translate(["mail me at third@example.com"], "en", "hi")) == 1
    )  # works after the failure


def test_gated_model_is_reported_as_an_access_problem(monkeypatch, settings):
    from lingua_bridge.errors import ModelAccessError

    def gated(*a, **k):
        raise OSError(
            "You are trying to access a gated repo. Make sure to have access to it at https://huggingface.co/x"
        )

    monkeypatch.setattr(transformers.AutoTokenizer, "from_pretrained", gated)
    with pytest.raises(ModelAccessError, match="lingua login"):
        _indic(settings).translate(["hello"], "en", "hi")


def test_opus_backend_prefixes_the_target_language_token(tiny, monkeypatch, settings):
    from lingua_bridge.translate.opus import OpusTranslator

    tok, model = tiny
    _patch_loaders(monkeypatch, tok, model)
    seen = []
    real_tok_call = type(tok).__call__
    monkeypatch.setattr(
        type(tok),
        "__call__",
        lambda self, text, *a, **k: (seen.append(list(text)), real_tok_call(self, text, *a, **k))[
            1
        ],
    )
    s = settings.model_copy(update={"device": "cpu", "max_new_tokens": 8, "num_beams": 1})
    o = OpusTranslator(s, ModelCache(1))
    assert o.supports("en", "zh") and o.supports("zh", "en") and not o.supports("en", "hi")
    assert len(o.translate(["hello"], "en", "zh")) == 1
    assert seen[0][0].startswith(">>cmn_Hans<< ")
    o.translate(["hello"], "zh", "en")
    assert not seen[1][0].startswith(">>")
