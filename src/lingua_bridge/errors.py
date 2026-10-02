"""Typed errors. The API maps each type to an HTTP status, the CLI to a readable message."""


class LinguaBridgeError(Exception):
    """Base class for every error this package raises on purpose."""

    code = "error"


class UnknownLanguageError(LinguaBridgeError):
    code = "unknown_language"


class UnsupportedPairError(LinguaBridgeError):
    code = "unsupported_pair"


class InputTooLongError(LinguaBridgeError):
    code = "input_too_long"


class DetectionError(LinguaBridgeError):
    code = "detection_failed"


class ConversionError(LinguaBridgeError):
    code = "conversion_failed"


class ModelUnavailableError(LinguaBridgeError):
    """A needed dependency or model could not be loaded (not installed, offline, out of memory)."""

    code = "model_unavailable"


class ModelAccessError(ModelUnavailableError):
    """The model exists but needs a Hugging Face login and acceptance of its terms (gated repo)."""

    code = "model_access"
