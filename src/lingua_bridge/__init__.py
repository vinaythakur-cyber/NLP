"""lingua-bridge: translation, transliteration and script conversion for Sanskrit, Hindi,
English and Chinese."""

from importlib.metadata import PackageNotFoundError, version

from .detect import detect
from .engine import LinguaBridge
from .languages import LANGUAGES, get_language
from .schemas import ConversionResult, DetectionResult, TranslationResult

try:
    __version__ = version("lingua-bridge")
except PackageNotFoundError:  # running from a source tree without installing
    __version__ = "0.1.0"

__all__ = [
    "LANGUAGES",
    "ConversionResult",
    "DetectionResult",
    "LinguaBridge",
    "TranslationResult",
    "__version__",
    "detect",
    "get_language",
]
