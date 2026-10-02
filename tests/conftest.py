import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from fakes import make_backends  # noqa: E402
from lingua_bridge.config import Settings  # noqa: E402
from lingua_bridge.engine import LinguaBridge  # noqa: E402


@pytest.fixture(autouse=True)
def _hermetic_environment(monkeypatch):
    """A developer's own LB_* variables (or .env) must never change test outcomes."""
    for key in [k for k in os.environ if k.startswith("LB_")]:
        monkeypatch.delenv(key)


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None)  # never read a developer's real .env in tests


@pytest.fixture
def backends():
    return make_backends()


@pytest.fixture
def engine(settings, backends) -> LinguaBridge:
    return LinguaBridge(settings, backends)
