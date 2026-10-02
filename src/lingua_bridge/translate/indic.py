"""IndicTrans2 backend: English <-> Hindi, English <-> Sanskrit, Hindi <-> Sanskrit."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from ..config import Settings
from ..errors import ModelUnavailableError
from ..languages import get_language
from .base import (
    INSTALL_HINT,
    ModelCache,
    import_torch,
    length_sorted_batches,
    load_error,
    resolve_device,
    resolve_dtype,
    safe_generate,
)

log = logging.getLogger(__name__)

_LANGS = {"sa", "hi", "en"}


@dataclass
class _Loaded:
    tokenizer: Any
    model: Any
    device: str


class IndicTranslator:
    name = "indictrans2"

    def __init__(self, settings: Settings, cache: ModelCache) -> None:
        self.settings = settings
        self.cache = cache

    def supports(self, src: str, tgt: str) -> bool:
        return src != tgt and src in _LANGS and tgt in _LANGS

    @staticmethod
    def _key(src: str, tgt: str) -> str:
        if src == "en":
            return "it2_en_indic"
        if tgt == "en":
            return "it2_indic_en"
        return "it2_indic_indic"

    def model_id(self, src: str, tgt: str) -> str:
        return self.settings.model_id(self._key(src, tgt))

    @staticmethod
    def _new_processor() -> Any:
        """A fresh processor per call (about 1 ms). It keeps a FIFO queue of placeholder maps between
        preprocess and postprocess, so sharing one across calls would let a failed generation leave
        stale maps behind and swap emails or URLs in the next call's output."""
        try:
            from ._indic_processor import IndicProcessor
        except ImportError as exc:
            raise ModelUnavailableError(
                f"Missing text-processing packages ({exc}). {INSTALL_HINT}"
            ) from exc
        return IndicProcessor(inference=True)

    def _load(self, model_id: str) -> _Loaded:
        import_torch()
        try:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        except ImportError as exc:
            raise ModelUnavailableError(f"transformers is not installed. {INSTALL_HINT}") from exc
        device = resolve_device(self.settings)
        dtype = resolve_dtype(self.settings, device)
        log.info("Loading %s on %s (%s)", model_id, device, str(dtype).replace("torch.", ""))
        try:
            tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
            model = AutoModelForSeq2SeqLM.from_pretrained(
                model_id, trust_remote_code=True, torch_dtype=dtype
            )
            model.to(device).eval()
        except Exception as exc:
            raise load_error(model_id, exc) from exc
        return _Loaded(tokenizer, model, device)

    def translate(self, texts: Sequence[str], src: str, tgt: str) -> list[str]:
        if not self.supports(src, tgt):
            raise ModelUnavailableError(f"IndicTrans2 does not support {src}->{tgt}")
        src_code, tgt_code = get_language(src).flores, get_language(tgt).flores
        model_id = self.model_id(src, tgt)
        out: list[str] = [""] * len(texts)
        with self.cache.lock:
            loaded: _Loaded = self.cache.get(model_id, lambda: self._load(model_id))
            ip = self._new_processor()
            for idx, batch in length_sorted_batches(texts, self.settings.batch_size):
                prepared = ip.preprocess_batch(batch, src_lang=src_code, tgt_lang=tgt_code)
                inputs = loaded.tokenizer(
                    prepared, padding="longest", truncation=True, max_length=256,
                    return_tensors="pt", return_attention_mask=True,
                ).to(loaded.device)  # fmt: skip
                generated = safe_generate(
                    loaded.model, inputs, use_cache=True, min_length=0,
                    max_length=self.settings.max_new_tokens,
                    num_beams=self.settings.num_beams, num_return_sequences=1,
                )  # fmt: skip
                decoded = loaded.tokenizer.batch_decode(
                    generated.detach().cpu().tolist(),
                    skip_special_tokens=True,
                    clean_up_tokenization_spaces=True,
                )
                for i, text in zip(idx, ip.postprocess_batch(decoded, lang=tgt_code), strict=True):
                    out[i] = text
        return out
