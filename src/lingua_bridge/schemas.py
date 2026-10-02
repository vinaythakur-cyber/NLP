"""Typed data contracts shared by the library, the API, the CLI and the tests."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------- results


class Candidate(BaseModel):
    language: str
    score: float


class DetectionResult(BaseModel):
    script: str = Field(description="Deva, Latn, Hans, Hant, Han (ambiguous), Mixed or Unknown")
    language: str | None = Field(description="Best guess: sa, hi, en, zh, or null when unknown")
    confidence: float = Field(ge=0, le=1)
    ambiguous: bool = Field(description="True when the top two candidates are too close to call")
    candidates: list[Candidate] = []
    latin_scheme: str | None = Field(
        default=None, description="For Latin text: iast, hk, hinglish or plain"
    )
    note: str | None = None


class Hop(BaseModel):
    src: str
    tgt: str
    backend: str
    model: str
    ms: float
    segments: int


class TranslationResult(BaseModel):
    text: str
    src: str
    tgt: str
    via: Literal["direct", "pivot", "identity"]
    route: list[Hop]
    detected: DetectionResult | None = None
    warnings: list[str] = []
    total_ms: float = 0.0


class ConversionOp(StrEnum):
    TRANSLITERATE = "transliterate"
    HINGLISH = "hinglish_to_devanagari"
    PINYIN = "pinyin"
    CHINESE_SCRIPT = "chinese_script"


Fidelity = Literal["lossless", "lossy", "best_effort"]


class ConversionResult(BaseModel):
    text: str
    op: ConversionOp
    fidelity: Fidelity
    backend: str | None = None
    note: str | None = None


# --------------------------------------------------------------- requests


class TranslateRequest(BaseModel):
    text: str = Field(min_length=1)
    src: str = "auto"
    tgt: str
    zh_variant: Literal["simplified", "traditional"] = "simplified"


class ConvertRequest(BaseModel):
    text: str = Field(min_length=1)
    op: ConversionOp
    source_scheme: str = "devanagari"
    target_scheme: str = "iast"
    pinyin_style: Literal["marks", "numbers", "plain"] = "marks"
    chinese_target: Literal["simplified", "traditional"] = "traditional"
    chinese_variant: Literal["standard", "taiwan", "hongkong"] = "standard"


class DetectRequest(BaseModel):
    text: str = Field(min_length=1)
