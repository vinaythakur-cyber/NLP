"""Command line: lingua translate | convert | detect | serve | download-models | doctor | languages."""

from __future__ import annotations

import json
import sys
import webbrowser
from collections.abc import Callable
from functools import lru_cache
from typing import Annotated, Any

import typer

from . import __version__
from ._logging import setup_logging
from .config import PROFILES, Settings, get_settings
from .engine import LinguaBridge
from .errors import LinguaBridgeError
from .languages import LANGUAGES
from .schemas import ConversionOp, ConvertRequest

app = typer.Typer(
    help="Translate and convert Sanskrit, Hindi, English and Chinese.", no_args_is_help=True
)
convert_app = typer.Typer(help="Script conversion (no translation).", no_args_is_help=True)
app.add_typer(convert_app, name="convert")


@lru_cache
def get_engine() -> LinguaBridge:
    setup_logging(get_settings().log_level)
    return LinguaBridge()


def _text(value: str) -> str:
    return sys.stdin.read() if value == "-" else value


def _guard(fn: Callable[[], Any]) -> Any:
    try:
        return fn()
    except LinguaBridgeError as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from None


def _emit(model: Any, as_json: bool, text: str) -> None:
    typer.echo(
        json.dumps(model.model_dump(mode="json"), ensure_ascii=False, indent=2) if as_json else text
    )


def _version(value: bool) -> None:
    if value:
        typer.echo(f"lingua-bridge {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[bool, typer.Option("--version", callback=_version, is_eager=True)] = False,
) -> None:
    """lingua-bridge command line."""


@app.command()
def translate(
    text: Annotated[str, typer.Argument(help='Text to translate, or "-" to read stdin.')],
    tgt: Annotated[str, typer.Option("--tgt", "-t", help="Target: sa, hi, en or zh.")],
    src: Annotated[str, typer.Option("--src", "-s", help="Source language, or auto.")] = "auto",
    zh: Annotated[
        str, typer.Option(help="Chinese output script: simplified or traditional.")
    ] = "simplified",
    as_json: Annotated[bool, typer.Option("--json", help="Print the full result as JSON.")] = False,
) -> None:
    """Translate text. Prints the route used on stderr so pivots through English are visible."""
    result = _guard(lambda: get_engine().translate(_text(text), src=src, tgt=tgt, zh_variant=zh))
    for w in result.warnings:
        typer.secho(f"note: {w}", fg=typer.colors.YELLOW, err=True)
    hops = " -> ".join(f"{h.src}->{h.tgt} [{h.backend}]" for h in result.route) or "none"
    typer.secho(
        f"route: {result.via} ({hops}), {result.total_ms:.0f} ms",
        fg=typer.colors.BRIGHT_BLACK,
        err=True,
    )
    _emit(result, as_json, result.text)


@app.command()
def detect(
    text: Annotated[str, typer.Argument(help='Text to inspect, or "-" for stdin.')],
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Detect script and language."""
    r = _guard(lambda: get_engine().detect(_text(text)))
    cands = ", ".join(f"{c.language} {c.score:.2f}" for c in r.candidates)
    amb = " (ambiguous)" if r.ambiguous else ""
    line = f"script={r.script} language={r.language} confidence={r.confidence:.2f}{amb}"
    line += f"\ncandidates: {cands}" if cands else ""
    line += f"\nnote: {r.note}" if r.note else ""
    _emit(r, as_json, line)


def _run_convert(req: ConvertRequest, as_json: bool) -> None:
    r = _guard(lambda: get_engine().convert(req))
    if r.note:
        typer.secho(f"{r.fidelity}: {r.note}", fg=typer.colors.BRIGHT_BLACK, err=True)
    _emit(r, as_json, r.text)


@convert_app.command("translit")
def convert_translit(
    text: Annotated[str, typer.Argument()],
    src: Annotated[
        str, typer.Option("--from", help="devanagari, iast, hk, itrans or roman.")
    ] = "devanagari",
    tgt: Annotated[str, typer.Option("--to")] = "iast",
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Devanagari <-> IAST / Harvard-Kyoto / ITRANS / casual Roman."""
    _run_convert(
        ConvertRequest(
            text=_text(text), op=ConversionOp.TRANSLITERATE, source_scheme=src, target_scheme=tgt
        ),
        as_json,
    )


@convert_app.command("hinglish")
def convert_hinglish(
    text: Annotated[str, typer.Argument()], as_json: Annotated[bool, typer.Option("--json")] = False
) -> None:
    """Roman Hindi (Hinglish) to Devanagari."""
    _run_convert(ConvertRequest(text=_text(text), op=ConversionOp.HINGLISH), as_json)


@convert_app.command("pinyin")
def convert_pinyin(
    text: Annotated[str, typer.Argument()],
    style: Annotated[str, typer.Option(help="marks (nǐ), numbers (ni3) or plain (ni).")] = "marks",
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Chinese characters to pinyin."""
    _run_convert(
        ConvertRequest(text=_text(text), op=ConversionOp.PINYIN, pinyin_style=style), as_json
    )  # type: ignore[arg-type]


@convert_app.command("script")
def convert_script(
    text: Annotated[str, typer.Argument()],
    to: Annotated[str, typer.Option("--to", help="simplified or traditional.")] = "traditional",
    variant: Annotated[str, typer.Option(help="standard, taiwan or hongkong.")] = "standard",
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Simplified <-> Traditional Chinese."""
    _run_convert(
        ConvertRequest(
            text=_text(text),
            op=ConversionOp.CHINESE_SCRIPT,
            chinese_target=to,
            chinese_variant=variant,
        ),  # type: ignore[arg-type]
        as_json,
    )


@app.command()
def languages() -> None:
    """List supported languages and their codes."""
    for lang in LANGUAGES.values():
        typer.echo(f"{lang.code}  {lang.flores:9} {lang.name} ({lang.native})")


@app.command()
def serve(
    host: Annotated[
        str | None, typer.Option(help="Default 127.0.0.1 (this computer only).")
    ] = None,
    port: Annotated[int | None, typer.Option()] = None,
    open_browser: Annotated[
        bool, typer.Option("--open", help="Open the web UI in your browser.")
    ] = False,
) -> None:
    """Start the API and web UI."""
    try:
        import uvicorn
    except ImportError:
        typer.secho(
            'The API needs extra packages: pip install -e ".[api]"', fg=typer.colors.RED, err=True
        )
        raise typer.Exit(code=2) from None
    s = get_settings()
    host, port = host or s.host, port or s.port
    url = f"http://{'localhost' if host in ('127.0.0.1', '0.0.0.0') else host}:{port}"
    typer.echo(f"lingua-bridge {__version__} serving at {url}  (API docs: {url}/docs)")
    if open_browser:
        webbrowser.open(url)
    uvicorn.run("lingua_bridge.api:app", host=host, port=port, log_level=s.log_level.lower())


def _download_patterns(model: str) -> list[str]:
    """Skip duplicate weight formats: if safetensors exist, ignore the .bin copies."""
    from huggingface_hub import HfApi

    try:
        names = [f.rfilename for f in HfApi().model_info(model).siblings or []]
    except Exception:
        return []
    patterns = [
        "*.h5",
        "*.msgpack",
        "*.onnx",
        "*.ot",
    ]  # TensorFlow / Flax / ONNX copies are never needed
    if any(n.endswith(".safetensors") for n in names):
        patterns.append("*.bin")  # PyTorch .bin duplicates the safetensors file
    return patterns


def _model_size_gb(model: str) -> float | None:
    from huggingface_hub import HfApi

    try:
        info = HfApi().model_info(model, files_metadata=True)
        skip = tuple(p.lstrip("*") for p in _download_patterns(model))
        total = sum((f.size or 0) for f in info.siblings or [] if not f.rfilename.endswith(skip))
        return total / 1e9
    except Exception:
        return None


@app.command("download-models")
def download_models(
    profile: Annotated[
        str, typer.Option(help="small (fits 4 GB GPUs) or base (1B+ models).")
    ] = "small",
    only: Annotated[str, typer.Option(help="all (IndicTrans2 + NLLB), it2, nllb or opus.")] = "all",
) -> None:
    """Download model weights now, with progress, instead of during the first translation."""
    if profile not in PROFILES:
        typer.secho(
            f"Unknown profile {profile!r}; choose from {', '.join(PROFILES)}.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        typer.secho(
            'Install the translation extras first: pip install -e ".[translate]"',
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2) from None
    s = Settings(profile=profile)  # type: ignore[arg-type]
    groups = {"it2": ["it2_en_indic", "it2_indic_en", "it2_indic_indic"], "nllb": ["nllb"],
              "opus": ["opus_en_zh", "opus_zh_en"]}  # fmt: skip
    keys = groups["it2"] + groups["nllb"] if only == "all" else groups.get(only, [])
    if not keys:
        typer.secho(
            f"Unknown --only {only!r}; choose all, it2, nllb or opus.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)
    skipped = 0
    for key in keys:
        model = s.model_id(key)
        size = _model_size_gb(model)
        typer.echo(f"Downloading {model}" + (f" (about {size:.1f} GB)" if size else "") + " ...")
        try:
            snapshot_download(model, ignore_patterns=_download_patterns(model) or None)
        except Exception as exc:
            from .translate.base import _is_gated

            if _is_gated(exc):
                skipped += 1
                typer.secho(
                    f"  No access to {model}: it is gated. See `lingua doctor` for the one-time steps; "
                    "NLLB is used instead until then.",
                    fg=typer.colors.YELLOW,
                    err=True,
                )
                continue
            typer.secho(
                f"Failed to download {model}: {exc}\nRun `lingua doctor` to check your connection.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1) from None
    done = (
        "All requested models are downloaded."
        if not skipped
        else f"Done, but {skipped} gated model(s) were skipped."
    )
    typer.secho(done, fg=typer.colors.GREEN if not skipped else typer.colors.YELLOW)


@app.command()
def login(
    token: Annotated[str | None, typer.Option(help="Read token; omit to be prompted.")] = None,
) -> None:
    """Save your Hugging Face token so gated models (IndicTrans2) can be downloaded."""
    try:
        from huggingface_hub import login as hf_login
    except ImportError:
        typer.secho(
            'Install the translation extras first: pip install -e ".[translate]"',
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2) from None
    token = token or typer.prompt(
        "Paste your Hugging Face read token (input is hidden)", hide_input=True
    )
    try:
        hf_login(token=token, add_to_git_credential=False)
    except Exception as exc:
        typer.secho(f"Login failed: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from None
    typer.secho("Token saved. Run `lingua doctor` to confirm access.", fg=typer.colors.GREEN)


@app.command()
def doctor(as_json: Annotated[bool, typer.Option("--json")] = False) -> None:
    """Check this machine and explain what, if anything, you need to do."""
    from .doctor import as_dicts, run_checks

    checks = run_checks()
    if as_json:
        typer.echo(json.dumps(as_dicts(checks), ensure_ascii=False, indent=2))
    else:
        tags = {"ok": ("[ OK ]", typer.colors.GREEN), "warn": ("[WARN]", typer.colors.YELLOW),
                "fail": ("[FAIL]", typer.colors.RED), "info": ("[INFO]", typer.colors.CYAN)}  # fmt: skip
        for c in checks:
            tag, colour = tags[c.status]
            typer.echo(typer.style(tag, fg=colour) + f" {c.name}: {c.detail}")
            if c.fix:
                typer.echo(f"        -> {c.fix}")
    if any(c.status == "fail" for c in checks):
        raise typer.Exit(code=1)
