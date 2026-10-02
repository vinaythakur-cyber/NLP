import json

import pytest
from typer.testing import CliRunner

from lingua_bridge import cli
from lingua_bridge.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _engine(monkeypatch, engine):
    monkeypatch.setattr(cli, "get_engine", lambda: engine)


def test_translate_prints_text_and_route():
    r = runner.invoke(app, ["translate", "मुझे चाय पसंद है।", "--src", "hi", "--tgt", "en"])
    assert r.exit_code == 0
    assert "[hi>en:it2]" in r.output and "route: direct" in r.output


def test_translate_pivot_route_is_shown():
    r = runner.invoke(app, ["translate", "रामः वनं गच्छति", "-s", "sa", "-t", "zh"])
    assert (
        r.exit_code == 0
        and "route: pivot" in r.output
        and "sa->en" in r.output
        and "en->zh" in r.output
    )


def test_translate_json():
    r = runner.invoke(app, ["translate", "hello", "-s", "en", "-t", "hi", "--json"])
    data = json.loads(r.stdout)
    assert data["via"] == "direct" and data["route"][0]["model"] == "fake/it2"


def test_translate_error_exit_code_and_message():
    r = runner.invoke(app, ["translate", "hello", "-s", "en", "-t", "fr"])
    assert r.exit_code == 2 and "Unknown language" in r.output


def test_translate_reads_stdin():
    r = runner.invoke(app, ["translate", "-", "-s", "en", "-t", "hi"], input="from stdin")
    assert r.exit_code == 0 and "from stdin" in r.output


def test_detect():
    r = runner.invoke(app, ["detect", "रामः वनं गच्छति"])
    assert r.exit_code == 0 and "language=sa" in r.output


@pytest.mark.parametrize(
    "args,expected",
    [
        (["convert", "translit", "संस्कृतम्", "--to", "iast"], "saṃskṛtam"),
        (["convert", "translit", "rAmaH", "--from", "hk", "--to", "devanagari"], "रामः"),
        (["convert", "hinglish", "mera naam"], "मेरा नाम"),
        (["convert", "pinyin", "你好", "--style", "numbers"], "ni3 hao3"),
        (["convert", "script", "我喜欢茶", "--to", "traditional"], "我喜歡茶"),
    ],
)
def test_convert_commands(args, expected):
    r = runner.invoke(app, args)
    assert r.exit_code == 0 and expected in r.output


def test_languages_and_version():
    r = runner.invoke(app, ["languages"])
    assert "san_Deva" in r.output and "zho_Hans" in r.output
    assert "lingua-bridge" in runner.invoke(app, ["--version"]).output


def test_doctor_runs_offline(monkeypatch):
    import urllib.error

    from lingua_bridge import doctor

    def offline(*a, **k):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(doctor.urllib.request, "urlopen", offline)
    r = runner.invoke(app, ["doctor"])
    assert r.exit_code == 0 and "Python" in r.output and "Hugging Face reachable" in r.output
    data = json.loads(runner.invoke(app, ["doctor", "--json"]).stdout)
    assert any(c["name"] == "Python" and c["status"] == "ok" for c in data)
