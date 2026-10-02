"""`lingua doctor`: checks the machine and says, in plain words, what to do about problems."""

from __future__ import annotations

import importlib
import importlib.util
import os
import platform
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import Settings, get_settings


@dataclass
class Check:
    name: str
    status: str  # ok | warn | fail | info
    detail: str
    fix: str = ""


def _have(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def _nvidia_smi() -> tuple[str, float] | None:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        out = subprocess.run(
            [exe, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout.strip().splitlines()[0]  # fmt: skip
        name, mem = [p.strip() for p in out.split(",")[:2]]
        return name, float(mem) / 1024
    except (subprocess.SubprocessError, OSError, ValueError, IndexError):
        return None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: object, **kwargs: object) -> None:  # type: ignore[override]
        return None


def hf_token() -> str | None:
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if token:
        return token
    try:
        from huggingface_hub import get_token

        return get_token()
    except Exception:
        return None


def hf_access(model_id: str) -> str:
    """'ok', 'denied' (gated/not accepted) or 'unreachable', via a HEAD request that does not follow redirects."""
    headers = {"Authorization": f"Bearer {hf_token()}"} if hf_token() else {}
    req = urllib.request.Request(
        f"https://huggingface.co/{model_id}/resolve/main/config.json",
        method="HEAD",
        headers=headers,
    )
    try:
        urllib.request.build_opener(_NoRedirect).open(req, timeout=8)
        return "ok"
    except urllib.error.HTTPError as exc:
        if exc.code in (301, 302, 303, 307, 308):
            return "ok"  # redirected to the file store: access granted
        return "denied" if exc.code in (401, 403) else "unreachable"
    except (urllib.error.URLError, OSError):
        return "unreachable"


def _hf_cache_dir() -> Path:
    try:
        from huggingface_hub import constants

        return Path(constants.HF_HUB_CACHE)
    except ImportError:
        return Path.home() / ".cache" / "huggingface" / "hub"


def run_checks(settings: Settings | None = None) -> list[Check]:
    s = settings or get_settings()
    checks: list[Check] = []

    ok = sys.version_info >= (3, 11)
    checks.append(Check("Python", "ok" if ok else "fail", f"{platform.python_version()} on {platform.system()}",
                        "" if ok else "Install Python 3.11 or newer from https://www.python.org/downloads/"))  # fmt: skip

    core = {"pydantic": "pydantic", "typer": "typer", "indic_transliteration": "indic-transliteration",
            "pypinyin": "pypinyin", "opencc": "opencc-python-reimplemented"}  # fmt: skip
    missing = [pkg for mod, pkg in core.items() if not _have(mod)]
    checks.append(Check("Conversion + detection packages", "fail" if missing else "ok",
                        "all installed" if not missing else "missing: " + ", ".join(missing),
                        'Run: pip install -e .' if missing else ""))  # fmt: skip

    api_missing = [m for m in ("fastapi", "uvicorn") if not _have(m)]
    checks.append(Check("API + web UI packages", "warn" if api_missing else "ok",
                        "all installed" if not api_missing else "missing: " + ", ".join(api_missing),
                        'Run: pip install -e ".[api]"' if api_missing else ""))  # fmt: skip

    tr_missing = [m for m in ("torch", "transformers", "sentencepiece", "regex", "sacremoses", "indicnlp")
                  if not _have(m)]  # fmt: skip
    checks.append(Check("Translation packages", "warn" if tr_missing else "ok",
                        "all installed" if not tr_missing else "missing: " + ", ".join(tr_missing),
                        'Translation will not work until you run: pip install -e ".[translate]"' if tr_missing else ""))  # fmt: skip

    gpu = _nvidia_smi()
    torch_cuda: bool | None = None
    if _have("torch"):
        try:
            import torch

            torch_cuda = bool(torch.cuda.is_available())
        except Exception:  # a broken torch install should not crash the doctor
            torch_cuda = None
    if gpu:
        name, vram = gpu
        checks.append(Check("NVIDIA GPU", "ok", f"{name}, {vram:.1f} GB VRAM"))
        if torch_cuda is False:
            checks.append(Check("PyTorch GPU support", "warn", "PyTorch is installed but cannot see the GPU (CPU-only build)",
                                "Reinstall a CUDA build: pip install --force-reinstall torch --index-url https://download.pytorch.org/whl/cu128 . Translation still works on CPU, just slowly."))  # fmt: skip
        elif torch_cuda:
            checks.append(Check("PyTorch GPU support", "ok", "PyTorch can use the GPU"))
        if s.profile == "base" and vram < 7:
            checks.append(Check("Model size vs VRAM", "warn", f"profile 'base' (1B+ models) on {vram:.1f} GB VRAM",
                                "Use LB_PROFILE=small, or expect out-of-memory errors."))  # fmt: skip
    else:
        checks.append(
            Check("NVIDIA GPU", "info", "none detected; translation will run on CPU (slower)")
        )

    hf_ok = False
    try:
        with urllib.request.urlopen("https://huggingface.co", timeout=6) as r:
            hf_ok = True
            checks.append(Check("Hugging Face reachable", "ok", f"HTTP {r.status}"))
    except (urllib.error.URLError, OSError) as exc:
        checks.append(Check("Hugging Face reachable", "warn", f"cannot reach huggingface.co ({exc})",
                            "Needed once to download models. Conversion and detection work without it. "
                            "On a restricted network set HF_ENDPOINT to a mirror."))  # fmt: skip

    if hf_ok:
        gated_id = s.model_id("it2_indic_indic")
        access = hf_access(gated_id)
        if access == "ok":
            checks.append(
                Check("IndicTrans2 access", "ok", f"Hugging Face grants access to {gated_id}")
            )
        elif access == "denied":
            checks.append(Check("IndicTrans2 access", "warn",
                                f"{gated_id} is gated and this machine is not authorized"
                                + (" (a token is set but access was not accepted)" if hf_token() else " (no token found)"),
                                "Translation still works through NLLB (lower quality, especially for Sanskrit). To enable "
                                f"IndicTrans2: log in at huggingface.co, open https://huggingface.co/{gated_id}, click "
                                "'Agree and access repository' (also for the en-indic and indic-en models), then run `lingua login`."))  # fmt: skip
        else:
            checks.append(Check("IndicTrans2 access", "info", "could not check"))

    cache = _hf_cache_dir()
    cached = sum((cache / ("models--" + s.model_id(k).replace("/", "--"))).is_dir()
                 for k in ("it2_en_indic", "it2_indic_en", "it2_indic_indic", "nllb"))  # fmt: skip
    checks.append(Check("Model cache", "ok" if cached == 4 else "info", f"{cached} of 4 models already downloaded ({cache})",
                        "" if cached == 4 else "Run `lingua download-models` to fetch them now, or they download on first use."))  # fmt: skip

    probe = cache if cache.exists() else Path.home()
    free = shutil.disk_usage(probe).free / 1e9
    checks.append(Check("Free disk space", "ok" if free > 8 else "warn", f"{free:.0f} GB free", "" if free > 8 else "Models need several GB."))  # fmt: skip

    from .convert.hinglish import get_backend

    try:
        checks.append(
            Check(
                "Hinglish engine",
                "info",
                f"{get_backend(s.hinglish_backend).name} (setting: {s.hinglish_backend})",
            )
        )
    except Exception as exc:
        checks.append(Check("Hinglish engine", "fail", str(exc), "Set LB_HINGLISH_BACKEND=rule"))
    return checks


def as_dicts(checks: list[Check]) -> list[dict[str, str]]:
    return [asdict(c) for c in checks]
