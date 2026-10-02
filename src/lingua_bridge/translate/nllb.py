"""NLLB-200 backend. Covers all four languages (FLORES codes san_Deva, hin_Deva, eng_Latn,
zho_Hans). NLLB weights are CC-BY-NC 4.0: non-commercial use only."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from ..config import Settings
from ..errors import ModelUnavailableError
from ..languages import LANGUAGES, get_language
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


@dataclass
class _Loaded:
    tokenizer: Any
    model: Any
    device: str


class NllbTranslator:
    name = "nllb"

    def __init__(self, settings: Settings, cache: ModelCache) -> None:
        self.settings = settings
        self.cache = cache

    def supports(self, src: str, tgt: str) -> bool:
        return src != tgt and src in LANGUAGES and tgt in LANGUAGES

    def model_id(self, src: str, tgt: str) -> str:
        return self.settings.model_id("nllb")

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
            tokenizer = AutoTokenizer.from_pretrained(model_id)
            model = AutoModelForSeq2SeqLM.from_pretrained(model_id, torch_dtype=dtype)
            model.to(device).eval()
        except Exception as exc:
            raise load_error(model_id, exc) from exc
        return _Loaded(tokenizer, model, device)

    def translate(self, texts: Sequence[str], src: str, tgt: str) -> list[str]:
        if not self.supports(src, tgt):
            raise ModelUnavailableError(f"{self.name} does not support {src}->{tgt}")
        src_code, tgt_code = get_language(src).flores, get_language(tgt).flores
        model_id = self.model_id(src, tgt)
        out: list[str] = [""] * len(texts)
        with self.cache.lock:
            loaded: _Loaded = self.cache.get(model_id, lambda: self._load(model_id))
            tok = loaded.tokenizer
            tok.src_lang = src_code
            forced_bos = tok.convert_tokens_to_ids(tgt_code)
            for idx, batch in length_sorted_batches(texts, self.settings.batch_size):
                inputs = tok(
                    list(batch), return_tensors="pt", padding=True, truncation=True, max_length=512
                ).to(loaded.device)
                generated = safe_generate(
                    loaded.model, inputs, forced_bos_token_id=forced_bos,
                    num_beams=self.settings.num_beams, max_new_tokens=self.settings.max_new_tokens,
                )  # fmt: skip
                decoded = tok.batch_decode(generated, skip_special_tokens=True)
                for i, text in zip(idx, decoded, strict=True):
                    out[i] = text
        return out
