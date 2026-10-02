"""Regenerate indic_processor_golden.json from the *compiled* IndicTransToolkit (Linux/macOS only).

    pip install --no-deps IndicTransToolkit && python tests/data/make_golden.py

The golden file is what tests/test_indic_processor.py holds our pure-Python port to.
"""

import glob
import importlib.util
import json
import sysconfig
from pathlib import Path

so = glob.glob(str(Path(sysconfig.get_paths()["purelib"]) / "IndicTransToolkit" / "processor*.so"))[
    0
]
spec = importlib.util.spec_from_file_location("processor", so)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

PRE = [
    (
        "eng_Latn",
        "hin_Deva",
        [
            "This is a test sentence.",
            "Please send an SMS to 9876543210 and an email on newemail123@xyz.com by 15th October, 2023.",
            "Visit https://example.com/page?id=5 now (it costs 50 %).",
            "He said “hello” – and left…",
        ],
    ),
    (
        "hin_Deva",
        "eng_Latn",
        ["मुझे चाय पसंद है।", "वह कल दिल्ली जाएगा, १२३ लोग आएंगे।", "ईमेल: a.b@site.org पर भेजें"],
    ),
    ("san_Deva", "hin_Deva", ["धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः ।", "रामः वनं गच्छति ।"]),
    ("hin_Deva", "san_Deva", ["राम वन जाता है।"]),
    ("san_Deva", "eng_Latn", ["सत्यमेव जयते ॥"]),
]
POST = [
    ("hin_Deva", ["यह एक परीक्षण वाक्य है।", "कृपया <ID1> पर संदेश भेजें ।", "नमस्ते , दुनिया !"]),
    ("san_Deva", ["रामः वनं गच्छति ।", "सत्यमेव जयते ॥"]),
    ("eng_Latn", ["This is a test sentence .", "Send mail to < ID1 > , please ."]),
]

golden = {"pre": [], "post": []}
for src, tgt, sents in PRE:
    ip = mod.IndicProcessor(inference=True)  # fresh instance: its placeholder queue is private
    golden["pre"].append(
        {
            "src": src,
            "tgt": tgt,
            "in": sents,
            "out": ip.preprocess_batch(sents, src_lang=src, tgt_lang=tgt),
        }
    )
for lang, sents in POST:
    # feed the processor placeholder maps the way a real preprocess call would
    ip = mod.IndicProcessor(inference=True)
    pre_in = [s.replace("<ID1>", "me@x.com") for s in sents]
    ip.preprocess_batch(pre_in, src_lang="eng_Latn", tgt_lang=lang)
    golden["post"].append(
        {"lang": lang, "pre_in": pre_in, "in": sents, "out": ip.postprocess_batch(sents, lang=lang)}
    )
Path(__file__).with_name("indic_processor_golden.json").write_text(
    json.dumps(golden, ensure_ascii=False, indent=1), encoding="utf8"
)
print(
    "wrote golden:",
    sum(len(x["out"]) for x in golden["pre"]),
    "pre,",
    sum(len(x["out"]) for x in golden["post"]),
    "post",
)
