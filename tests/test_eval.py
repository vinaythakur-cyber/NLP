import io
import sys
import tarfile
from pathlib import Path

import pytest

from fakes import make_backends

pytest.importorskip("sacrebleu")
sys.path.insert(0, str(Path(__file__).parent.parent / "eval"))
import fetch_data  # noqa: E402
import run_eval  # noqa: E402
from lingua_bridge.translate.router import Router  # noqa: E402


def make_tar(layout: str) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for code in fetch_data.CODES:
            for split in ("dev", "devtest"):
                data = f"{code} line one\n{code} line two\n".encode()
                info = tarfile.TarInfo(layout.format(split=split, code=code))
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


@pytest.mark.parametrize("layout", ["flores200_dataset/{split}/{code}.{split}", "{code}.{split}"])
def test_fetch_extracts_wanted_files_whatever_the_layout(tmp_path, layout):
    written = fetch_data.extract(make_tar(layout), tmp_path)
    assert len(written) == 8
    assert (tmp_path / "devtest" / "san_Deva.devtest").read_text().startswith("san_Deva line one")


def test_fetch_reports_missing_files(tmp_path):
    with pytest.raises(SystemExit, match="missing"):
        fetch_data.extract(
            make_tar("x/{split}/{code}.{split}")[:0] or make_tar("x/{split}/other.{split}"),
            tmp_path,
        )


def test_load_flores_respects_limit_and_reports_missing(tmp_path):
    (tmp_path / "devtest").mkdir()
    (tmp_path / "devtest" / "eng_Latn.devtest").write_text("a\nb\nc\n", encoding="utf8")
    assert run_eval.load_flores(tmp_path, "devtest", "en", 2) == ["a", "b"]
    with pytest.raises(SystemExit, match="fetch_data"):
        run_eval.load_flores(tmp_path, "devtest", "hi", None)


def test_perfect_translation_scores_100_and_markdown_is_written_from_results():
    hyps = refs = ["我喜欢喝茶。", "你好，世界。"]
    chrf, bleu, chrf_sig, bleu_sig = run_eval.score(hyps, refs, "zh")
    assert (
        round(chrf) == 100 and round(bleu) == 100 and "nw:2" in chrf_sig and "tok:zh" in bleu_sig
    )  # nw:2 means chrF++


def test_candidates_offer_alternatives_only_when_comparing():
    router = Router(make_backends() | {"opus": make_backends()["zh"]})
    assert run_eval.candidates(router, "sa", "en", compare=False) == ["(default)"]
    assert run_eval.candidates(router, "sa", "en", compare=True) == ["(default)", "nllb"]
    assert "pivot" not in run_eval.candidates(router, "sa", "zh", compare=True)
    assert "direct" in run_eval.candidates(router, "sa", "zh", compare=True)  # default is a pivot
    assert "pivot" in run_eval.candidates(router, "hi", "zh", compare=True)  # default is direct


def test_evaluate_pair_and_render(tmp_path):
    router = Router(make_backends())
    srcs = ["hello", "world"]
    refs = ["[en>zh:zh] hello", "[en>zh:zh] world"]  # the fake translator's exact output
    r, chrf_sig, bleu_sig, texts = run_eval.evaluate_pair(
        router, "en", "zh", srcs, refs, "(default)"
    )
    assert texts == refs and r.chrf_pp == 100.0 and r.via == "direct" and r.n == 2
    nllb, *_ = run_eval.evaluate_pair(router, "en", "zh", srcs, refs, "nllb")
    assert nllb.route != r.route
    meta = {
        "date": "2026-01-01",
        "split": "devtest",
        "n": 2,
        "profile": "small",
        "device": "cpu",
        "beams": 4,
        "dtype": "auto",
    }
    md = run_eval.render_markdown(
        [r, nllb], meta, (chrf_sig, bleu_sig), {("en", "zh"): "(default)"}
    )
    assert "| en → zh |" in md and "★" in md and "nothing is hand-edited" in md and chrf_sig in md
