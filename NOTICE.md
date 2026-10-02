# Third-party notices

lingua-bridge's own code is MIT-licensed (see LICENSE). Model weights and data it can
download keep their own licenses. Check them before any commercial use.

| Component | License | Source |
|---|---|---|
| IndicTrans2 checkpoints (`ai4bharat/indictrans2-*`) | MIT | https://github.com/AI4Bharat/IndicTrans2 (README, License section) |
| NLLB-200 checkpoints (`facebook/nllb-200-*`) | **CC-BY-NC 4.0 (non-commercial)** | https://github.com/facebookresearch/fairseq/tree/nllb (README) |
| FLORES-200 evaluation data | see the dataset page | https://github.com/facebookresearch/flores |
| `src/lingua_bridge/translate/_indic_processor.py` | MIT, derived from IndicTransToolkit by Varun Gumma | https://github.com/VarunGumma/IndicTransToolkit |
| indic-transliteration, pypinyin, opencc-python-reimplemented | MIT / MIT / Apache-2.0 | PyPI |

The pure-Python port in `_indic_processor.py` follows `IndicTransToolkit/processor.pyx`
(MIT, Copyright (c) Varun Gumma). The original copyright and permission notice
applies to that file.
