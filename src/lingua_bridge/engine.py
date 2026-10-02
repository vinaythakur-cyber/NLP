"""The library's front door: detection, conversion and translation behind one object.

The CLI, the API and the web page all call this class and contain no logic of their own.
Translation backends load lazily, so creating a LinguaBridge is instant and needs no models.
"""

from __future__ import annotations

import time
from collections.abc import Mapping

from .config import Settings, get_settings
from .convert import chinese as zh_tools
from .convert import devanagari as deva_tools
from .convert.hinglish import get_backend
from .detect import detect as detect_text
from .detect import script_shares
from .errors import ConversionError, DetectionError, InputTooLongError
from .languages import get_language
from .schemas import (
    ConversionOp,
    ConversionResult,
    ConvertRequest,
    DetectionResult,
    TranslationResult,
)
from .translate._text import join_text, split_text
from .translate.base import ModelCache, Translator
from .translate.indic import IndicTranslator
from .translate.nllb import NllbTranslator
from .translate.opus import OpusTranslator
from .translate.router import Router
from .translate.zh import ChineseTranslator


class LinguaBridge:
    def __init__(
        self, settings: Settings | None = None, backends: Mapping[str, Translator] | None = None
    ) -> None:
        self.settings = settings or get_settings()
        self.cache = ModelCache(self.settings.max_loaded_models)
        if backends is None:
            backends = {
                "indictrans2": IndicTranslator(self.settings, self.cache),
                "zh": ChineseTranslator(self.settings, self.cache),
                "nllb": NllbTranslator(self.settings, self.cache),
                "opus": OpusTranslator(self.settings, self.cache),
            }
        self.backends = dict(backends)
        nllb_only = self.settings.translation_engine == "nllb"
        self.router = Router(
            self.backends,
            self.settings.parsed_route_overrides(),
            preference=("nllb",) if nllb_only else ("indictrans2", "zh", "nllb"),
            pivot_by_default=not nllb_only,
            fallback_to_nllb=self.settings.fallback_to_nllb,
        )

    # ------------------------------------------------------------ detection

    def detect(self, text: str) -> DetectionResult:
        return detect_text(text)

    # ----------------------------------------------------------- conversion

    def convert(self, req: ConvertRequest) -> ConversionResult:
        if req.op == ConversionOp.TRANSLITERATE:
            src, tgt = (
                deva_tools.parse_scheme(req.source_scheme),
                deva_tools.parse_scheme(req.target_scheme),
            )
            fid = deva_tools.fidelity_for(src, tgt)
            note = {
                "lossy": "Casual Roman drops distinctions (long vowels, retroflex letters); it cannot be reversed exactly.",
                "best_effort": "Roman input is spelling prediction, not a fixed mapping.",
            }.get(fid)
            return ConversionResult(
                text=deva_tools.transliterate(req.text, src, tgt),
                op=req.op,
                fidelity=fid,
                note=note,
            )
        if req.op == ConversionOp.HINGLISH:
            backend = get_backend(self.settings.hinglish_backend)
            return ConversionResult(
                text=backend.convert(req.text), op=req.op, fidelity="best_effort", backend=backend.name,
                note="Roman Hindi spelling is not standardized; treat the result as a suggestion.",
            )  # fmt: skip
        if req.op == ConversionOp.PINYIN:
            return ConversionResult(
                text=zh_tools.to_pinyin(req.text, req.pinyin_style), op=req.op, fidelity="lossy",
                note="Many characters share one pinyin spelling, and tones may be dropped.",
            )  # fmt: skip
        if req.op == ConversionOp.CHINESE_SCRIPT:
            fn = (
                zh_tools.to_traditional
                if req.chinese_target == "traditional"
                else zh_tools.to_simplified
            )
            return ConversionResult(
                text=fn(req.text, req.chinese_variant), op=req.op, fidelity="best_effort",
                note="Several traditional characters merged into one simplified character, so the reverse is a choice.",
            )  # fmt: skip
        raise ConversionError(f"Unknown conversion operation {req.op!r}")

    # ---------------------------------------------------------- translation

    def _normalize_source(
        self, text: str, src: str, det: DetectionResult | None, warnings: list[str]
    ) -> str:
        """Bring the input into the form the models expect (Devanagari, Simplified)."""
        if src in ("sa", "hi") and script_shares(text).get("Latn", 0) > 0.5:
            scheme = det.latin_scheme if det else None
            if scheme in ("iast", "hk"):
                warnings.append(
                    f"Input was romanized ({scheme.upper()}); converted to Devanagari first."
                )
                return deva_tools.to_devanagari(text, scheme)
            if src == "sa":
                warnings.append(
                    "Latin-script Sanskrit assumed to be ITRANS; converted to Devanagari first."
                )
                return deva_tools.to_devanagari(text, "itrans")
            warnings.append("Romanized Hindi converted with the Hinglish engine (best effort).")
            return get_backend(self.settings.hinglish_backend).convert(text)
        if src == "zh":
            simp, trad = zh_tools.script_counts(text)
            if trad > simp:
                warnings.append(
                    "Traditional Chinese input converted to Simplified before translation."
                )
                return zh_tools.to_simplified(text)
        return text

    def translate(
        self, text: str, src: str = "auto", tgt: str = "en", zh_variant: str = "simplified"
    ) -> TranslationResult:
        started = time.perf_counter()
        if len(text) > self.settings.max_input_chars:
            raise InputTooLongError(
                f"Input has {len(text)} characters; the limit is {self.settings.max_input_chars} "
                "(LB_MAX_INPUT_CHARS)."
            )
        tgt_code = get_language(tgt).code
        warnings: list[str] = []
        detected: DetectionResult | None = None
        try:
            det = detect_text(text)
        except DetectionError:
            det = None
        if src.strip().lower() == "auto":
            if det is None or det.language is None:
                raise DetectionError("Could not detect the source language; pass --src explicitly.")
            detected, src_code = det, det.language
            if det.ambiguous:
                warnings.append(
                    f"Source language guessed as {src_code} but the evidence is weak "
                    f"(confidence {det.confidence:.2f}); pass src explicitly to be sure."
                )
        else:
            src_code = get_language(src).code

        prepared = self._normalize_source(text, src_code, det, warnings)
        if src_code == tgt_code:
            warnings.append("Source and target are the same language; nothing was translated.")
        segments, layout = split_text(prepared)
        routed = self.router.translate(segments, src_code, tgt_code)
        warnings.extend(routed.warnings)
        out = join_text(routed.texts, layout, tgt_code) if segments else prepared
        if tgt_code == "zh" and zh_variant == "traditional" and routed.via != "identity":
            out = zh_tools.to_traditional(out)
        return TranslationResult(
            text=out, src=src_code, tgt=tgt_code, via=routed.via, route=routed.hops, detected=detected,
            warnings=warnings, total_ms=round((time.perf_counter() - started) * 1000, 1),
        )  # fmt: skip

    # ------------------------------------------------------------- inspection

    def model_status(self) -> list[dict[str, object]]:
        """Which model ids the current settings point at, and which are in memory right now."""
        loaded = set(self.cache.loaded())
        keys = (
            "it2_en_indic",
            "it2_indic_en",
            "it2_indic_indic",
            "nllb",
            "opus_en_zh",
            "opus_zh_en",
        )
        return [
            {
                "key": k,
                "model": self.settings.model_id(k),
                "loaded": self.settings.model_id(k) in loaded,
            }
            for k in keys
        ]
