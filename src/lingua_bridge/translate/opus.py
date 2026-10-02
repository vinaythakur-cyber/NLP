"""Helsinki-NLP opus-mt backend for English <-> Chinese only (Marian models, ungated).

Model cards: opus-mt-zh-en (CC-BY-4.0) and opus-mt-en-zh (Apache-2.0). The en->zh model needs a
target-language token in front of the source, ">>cmn_Hans<<". Not used by default; select it
per pair with LB_ROUTE_OVERRIDES='{"en>zh": "opus", "zh>en": "opus"}' and compare with
eval/run_eval.py.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from ..config import Settings
from ..errors import ModelUnavailableError
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


class OpusTranslator:
    name = "opus"

    def __init__(self, settings: Settings, cache: ModelCache) -> None:
        self.settings = settings
        self.cache = cache

    def supports(self, src: str, tgt: str) -> bool:
        return (src, tgt) in {("en", "zh"), ("zh", "en")}

    def model_id(self, src: str, tgt: str) -> str:
        return self.settings.model_id("opus_en_zh" if src == "en" else "opus_zh_en")

    def _load(self, model_id: str) -> _Loaded:
        import_torch()
        try:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        except ImportError as exc:
            raise ModelUnavailableError(f"transformers is not installed. {INSTALL_HINT}") from exc
        device = resolve_device(self.settings)
        dtype = resolve_dtype(self.settings, device)
        log.info("Loading %s on %s", model_id, device)
        try:
            tokenizer = AutoTokenizer.from_pretrained(model_id)
            model = AutoModelForSeq2SeqLM.from_pretrained(model_id, torch_dtype=dtype)
            model.to(device).eval()
        except Exception as exc:
            raise load_error(model_id, exc) from exc
        return _Loaded(tokenizer, model, device)

    def translate(self, texts: Sequence[str], src: str, tgt: str) -> list[str]:
        if not self.supports(src, tgt):
            raise ModelUnavailableError(f"opus does not support {src}->{tgt}")
        model_id = self.model_id(src, tgt)
        prefix = ">>cmn_Hans<< " if tgt == "zh" else ""
        out: list[str] = [""] * len(texts)
        with self.cache.lock:
            loaded: _Loaded = self.cache.get(model_id, lambda: self._load(model_id))
            for idx, batch in length_sorted_batches(
                [prefix + t for t in texts], self.settings.batch_size
            ):
                inputs = loaded.tokenizer(
                    batch, return_tensors="pt", padding=True, truncation=True, max_length=512
                ).to(loaded.device)
                generated = safe_generate(
                    loaded.model, inputs, num_beams=self.settings.num_beams,
                    max_new_tokens=self.settings.max_new_tokens,
                )  # fmt: skip
                decoded = loaded.tokenizer.batch_decode(generated, skip_special_tokens=True)
                for i, text in zip(idx, decoded, strict=True):
                    out[i] = text
        return out
