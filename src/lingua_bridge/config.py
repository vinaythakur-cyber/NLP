"""Settings from environment variables (prefix LB_) or a .env file. See .env.example."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Literal

from dotenv import find_dotenv, load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Make a .env file in the working directory visible to libraries that read os.environ directly
# (HF_TOKEN, HF_HOME, ...). Real environment variables always win.
load_dotenv(find_dotenv(usecwd=True), override=False)

# Model ids per profile. "small" fits a 4 GB GPU; "base" needs more VRAM.
PROFILES: dict[str, dict[str, str]] = {
    "small": {
        "it2_en_indic": "ai4bharat/indictrans2-en-indic-dist-200M",
        "it2_indic_en": "ai4bharat/indictrans2-indic-en-dist-200M",
        "it2_indic_indic": "ai4bharat/indictrans2-indic-indic-dist-320M",
        "nllb": "facebook/nllb-200-distilled-600M",
        "opus_en_zh": "Helsinki-NLP/opus-mt-en-zh",
        "opus_zh_en": "Helsinki-NLP/opus-mt-zh-en",
    },
    "base": {
        "it2_en_indic": "ai4bharat/indictrans2-en-indic-1B",
        "it2_indic_en": "ai4bharat/indictrans2-indic-en-1B",
        "it2_indic_indic": "ai4bharat/indictrans2-indic-indic-1B",
        "nllb": "facebook/nllb-200-distilled-1.3B",
        "opus_en_zh": "Helsinki-NLP/opus-mt-en-zh",
        "opus_zh_en": "Helsinki-NLP/opus-mt-zh-en",
    },
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LB_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # models and hardware
    profile: Literal["small", "base"] = "small"
    device: Literal["auto", "cuda", "cpu"] = "auto"
    dtype: Literal["auto", "float32", "float16", "bfloat16"] = "auto"
    max_loaded_models: int = Field(default=2, ge=1)
    it2_en_indic_model: str | None = None
    it2_indic_en_model: str | None = None
    it2_indic_indic_model: str | None = None
    nllb_model: str | None = None
    opus_en_zh_model: str | None = None
    opus_zh_en_model: str | None = None

    # generation
    num_beams: int = Field(default=4, ge=1)
    max_new_tokens: int = Field(default=256, ge=8)
    batch_size: int = Field(default=8, ge=1)
    max_input_chars: int = Field(default=5000, ge=1)

    # routing: JSON like {"sa>zh": "direct", "sa>en": "nllb", "en>zh": "opus"}
    route_overrides: str = ""
    # "auto": IndicTrans2 for sa/hi/en pairs, NLLB for Chinese pairs. "nllb": NLLB for everything
    # (no Hugging Face login needed, lower Sanskrit quality).
    translation_engine: Literal["auto", "nllb"] = "auto"
    # If an IndicTrans2 model is gated and you are not logged in, use NLLB for that hop and warn.
    fallback_to_nllb: bool = True

    # conversion
    hinglish_backend: Literal["auto", "rule", "ai4bharat"] = "auto"

    # server
    host: str = "127.0.0.1"
    port: int = 8000
    web_dir: str = ""
    log_level: str = "INFO"

    def model_id(self, key: str) -> str:
        """Model id for a key such as 'nllb' or 'it2_indic_en', honoring explicit overrides."""
        override = getattr(self, f"{key}_model")
        return override or PROFILES[self.profile][key]

    def parsed_route_overrides(self) -> dict[str, str]:
        if not self.route_overrides.strip():
            return {}
        data = json.loads(self.route_overrides)
        if not isinstance(data, dict):
            raise ValueError("LB_ROUTE_OVERRIDES must be a JSON object")
        return {str(k): str(v) for k, v in data.items()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
