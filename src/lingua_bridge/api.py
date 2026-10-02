"""FastAPI service: POST /translate, /convert, /detect and GET /healthz, /languages, /models.

This file only validates requests, calls LinguaBridge and maps errors to HTTP status codes.
It also serves the web UI from ./web at "/".
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from ._logging import setup_logging
from .config import Settings, get_settings
from .engine import LinguaBridge
from .errors import (
    ConversionError,
    DetectionError,
    InputTooLongError,
    LinguaBridgeError,
    ModelUnavailableError,
    UnknownLanguageError,
    UnsupportedPairError,
)
from .languages import LANGUAGES
from .schemas import (
    ConversionResult,
    ConvertRequest,
    DetectionResult,
    DetectRequest,
    TranslateRequest,
    TranslationResult,
)

_STATUS = {
    UnknownLanguageError: 422,
    UnsupportedPairError: 422,
    DetectionError: 422,
    ConversionError: 422,
    InputTooLongError: 413,
    ModelUnavailableError: 503,
}


def find_web_dir(settings: Settings) -> Path | None:
    candidates = [Path(settings.web_dir)] if settings.web_dir else []
    candidates += [Path(__file__).resolve().parents[2] / "web", Path.cwd() / "web"]
    return next((p for p in candidates if (p / "index.html").is_file()), None)


def _device_summary() -> str:
    try:
        import torch
    except ImportError:
        return "torch not installed (conversion and detection only)"
    if torch.cuda.is_available():
        return f"cuda: {torch.cuda.get_device_name(0)}"
    return "cpu"


def create_app(engine: LinguaBridge | None = None) -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)
    engine = engine or LinguaBridge(settings)
    app = FastAPI(
        title="lingua-bridge",
        version=__version__,
        description="Translation and script conversion for Sanskrit, Hindi, English and Chinese.",
    )
    app.state.engine = engine

    @app.exception_handler(LinguaBridgeError)
    async def _handle(_: Request, exc: LinguaBridgeError) -> JSONResponse:
        status = next((s for cls, s in _STATUS.items() if isinstance(exc, cls)), 400)
        return JSONResponse(status_code=status, content={"error": exc.code, "message": str(exc)})

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/languages")
    def languages() -> list[dict[str, str]]:
        return [
            {"code": lang.code, "flores": lang.flores, "name": lang.name, "native": lang.native}
            for lang in LANGUAGES.values()
        ]

    @app.get("/models")
    def models() -> dict[str, object]:
        return {
            "profile": engine.settings.profile,
            "device": _device_summary(),
            "models": engine.model_status(),
        }

    @app.post("/translate", response_model=TranslationResult)
    def translate(req: TranslateRequest) -> TranslationResult:
        return engine.translate(req.text, src=req.src, tgt=req.tgt, zh_variant=req.zh_variant)

    @app.post("/convert", response_model=ConversionResult)
    def convert(req: ConvertRequest) -> ConversionResult:
        return engine.convert(req)

    @app.post("/detect", response_model=DetectionResult)
    def detect(req: DetectRequest) -> DetectionResult:
        return engine.detect(req.text)

    web = find_web_dir(settings)
    if web is not None:  # mounted last so the API routes above win
        app.mount("/", StaticFiles(directory=web, html=True), name="web")
    return app


app = create_app()
