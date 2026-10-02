"""Chinese-pair backend: NLLB-200 restricted to pairs that involve Chinese.

IndicTrans2 has no Chinese, so every pair with zh needs a different model family. NLLB-200
lists zho_Hans/zho_Hant plus Hindi, Sanskrit and English, so one model covers all of them.
Simplified/Traditional handling lives in the engine, not here.
"""

from __future__ import annotations

from .nllb import NllbTranslator


class ChineseTranslator(NllbTranslator):
    name = "zh"

    def supports(self, src: str, tgt: str) -> bool:
        return super().supports(src, tgt) and "zh" in (src, tgt)
