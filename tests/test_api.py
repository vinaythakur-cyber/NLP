import pytest
from fastapi.testclient import TestClient

from fakes import FakeTranslator, make_backends
from lingua_bridge.api import create_app
from lingua_bridge.config import Settings
from lingua_bridge.engine import LinguaBridge
from lingua_bridge.errors import ModelUnavailableError


@pytest.fixture
def client(engine):
    return TestClient(create_app(engine))


def post(client, path, **body):
    return client.post(path, json=body)


def test_health_languages_models(client):
    assert client.get("/healthz").json()["status"] == "ok"
    codes = [lang["code"] for lang in client.get("/languages").json()]
    assert codes == ["sa", "hi", "en", "zh"]
    models = client.get("/models").json()
    assert models["profile"] == "small" and len(models["models"]) >= 4


def test_translate(client):
    r = post(client, "/translate", text="मुझे चाय पसंद है।", src="hi", tgt="en")
    assert r.status_code == 200
    body = r.json()
    assert body["via"] == "direct" and body["route"][0]["backend"] == "indictrans2"
    assert body["text"].startswith("[hi>en:it2]")


def test_translate_pivot_is_visible_in_the_response(client):
    body = post(client, "/translate", text="रामः वनं गच्छति", src="sa", tgt="zh").json()
    assert body["via"] == "pivot" and len(body["route"]) == 2


@pytest.mark.parametrize(
    "payload,status,code",
    [
        ({"text": "x", "src": "en", "tgt": "fr"}, 422, "unknown_language"),
        ({"text": "12345", "src": "auto", "tgt": "en"}, 422, "detection_failed"),
        ({"text": "", "tgt": "en"}, 422, None),
        ({"src": "en", "tgt": "hi"}, 422, None),
        ({"text": "x", "tgt": "zh", "zh_variant": "klingon"}, 422, None),
    ],
)
def test_translate_errors(client, payload, status, code):
    r = client.post("/translate", json=payload)
    assert r.status_code == status
    if code:
        assert r.json()["error"] == code


def test_input_too_long_is_413(backends):
    eng = LinguaBridge(Settings(_env_file=None, max_input_chars=5), backends)
    r = post(TestClient(create_app(eng)), "/translate", text="x" * 6, src="en", tgt="hi")
    assert r.status_code == 413 and r.json()["error"] == "input_too_long"


def test_model_unavailable_is_503_with_a_helpful_message():
    eng = LinguaBridge(Settings(_env_file=None), make_backends(
        indictrans2=FakeTranslator("it2", error=ModelUnavailableError("PyTorch is not installed.")),
        nllb=FakeTranslator("nllb", error=ModelUnavailableError("PyTorch is not installed."))))  # fmt: skip
    r = post(TestClient(create_app(eng)), "/translate", text="x", src="en", tgt="hi")
    assert r.status_code == 503 and "PyTorch" in r.json()["message"]


def test_detect(client):
    body = post(client, "/detect", text="धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः").json()
    assert body["language"] == "sa" and body["script"] == "Deva"


def test_convert_each_operation(client):
    assert (
        post(
            client,
            "/convert",
            text="संस्कृतम्",
            op="transliterate",
            source_scheme="devanagari",
            target_scheme="hk",
        ).json()["text"]
        == "saMskRtam"
    )
    assert (
        post(client, "/convert", text="mera naam", op="hinglish_to_devanagari").json()["text"]
        == "मेरा नाम"
    )
    assert (
        post(client, "/convert", text="你好", op="pinyin", pinyin_style="plain").json()["text"]
        == "ni hao"
    )
    assert (
        post(
            client, "/convert", text="我喜欢茶", op="chinese_script", chinese_target="traditional"
        ).json()["text"]
        == "我喜歡茶"
    )


def test_convert_unknown_scheme_is_422(client):
    r = post(
        client,
        "/convert",
        text="x",
        op="transliterate",
        source_scheme="klingon",
        target_scheme="iast",
    )
    assert r.status_code == 422 and r.json()["error"] == "conversion_failed"


def test_web_ui_and_docs_are_served(client):
    index = client.get("/")
    assert index.status_code == 200 and "lingua-bridge" in index.text
    assert client.get("/app.js").status_code == 200
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").json()["info"]["title"] == "lingua-bridge"
