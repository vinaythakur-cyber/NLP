import pytest

from lingua_bridge.config import PROFILES, Settings
from lingua_bridge.errors import UnknownLanguageError
from lingua_bridge.languages import LANGUAGES, all_pairs, get_language


def test_four_languages_and_twelve_pairs():
    assert set(LANGUAGES) == {"sa", "hi", "en", "zh"}
    assert len(all_pairs()) == 12


@pytest.mark.parametrize(
    "alias,code",
    [("Sanskrit", "sa"), ("hin_Deva", "hi"), ("ENG", "en"), ("zh-Hans", "zh"), (" cmn ", "zh")],
)
def test_aliases_resolve(alias, code):
    assert get_language(alias).code == code


def test_flores_codes():
    assert [get_language(c).flores for c in ("sa", "hi", "en", "zh")] == [
        "san_Deva",
        "hin_Deva",
        "eng_Latn",
        "zho_Hans",
    ]


def test_unknown_language_lists_valid_codes():
    with pytest.raises(UnknownLanguageError, match="sa, hi, en, zh"):
        get_language("fr")


def test_settings_defaults_and_profiles():
    s = Settings(_env_file=None)
    assert s.profile == "small" and s.device == "auto" and s.fallback_to_nllb
    assert s.model_id("nllb") == PROFILES["small"]["nllb"]
    assert Settings(_env_file=None, profile="base").model_id("it2_indic_en").endswith("indic-en-1B")


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("LB_PROFILE", "base")
    monkeypatch.setenv("LB_NLLB_MODEL", "my/own-nllb")
    monkeypatch.setenv("LB_ROUTE_OVERRIDES", '{"sa>zh": "direct"}')
    s = Settings(_env_file=None)
    assert s.profile == "base"
    assert s.model_id("nllb") == "my/own-nllb"
    assert s.parsed_route_overrides() == {"sa>zh": "direct"}


def test_route_overrides_must_be_a_json_object():
    with pytest.raises(ValueError):
        Settings(_env_file=None, route_overrides="[1,2]").parsed_route_overrides()
    assert Settings(_env_file=None).parsed_route_overrides() == {}
