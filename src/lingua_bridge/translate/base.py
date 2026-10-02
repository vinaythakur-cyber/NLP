"""Translator interface plus the shared runtime helpers (device, model cache, safe generation)."""

from __future__ import annotations

import gc
import logging
import sys
import threading
from collections import OrderedDict
from collections.abc import Callable, Iterator, Sequence
from typing import Any, Protocol

from ..config import Settings
from ..errors import ModelAccessError, ModelUnavailableError

log = logging.getLogger(__name__)

INSTALL_HINT = 'Install the translation extras with:  pip install -e ".[translate]"  (or start the app with run.bat / run.sh without --light)'


class Translator(Protocol):
    """Every model wrapper implements this. The router and the tests only know this interface."""

    name: str

    def supports(self, src: str, tgt: str) -> bool: ...

    def model_id(self, src: str, tgt: str) -> str: ...

    def translate(self, texts: Sequence[str], src: str, tgt: str) -> list[str]: ...


def import_torch() -> Any:
    try:
        import torch
    except ImportError as exc:
        raise ModelUnavailableError(f"PyTorch is not installed. {INSTALL_HINT}") from exc
    return torch


def resolve_device(settings: Settings) -> str:
    if settings.device != "auto":
        return settings.device
    return "cuda" if import_torch().cuda.is_available() else "cpu"


def resolve_dtype(settings: Settings, device: str) -> Any:
    torch = import_torch()
    if settings.dtype != "auto":
        return getattr(torch, settings.dtype)
    return torch.float16 if device == "cuda" else torch.float32


class ModelCache:
    """Keeps at most N models in memory (least recently used leave first).

    A 4 GB GPU cannot hold every model at once, so we load on demand and evict. One lock
    serializes loading and generation: a single GPU does not run concurrent requests faster.
    """

    def __init__(self, max_loaded: int = 2) -> None:
        self.max_loaded = max_loaded
        self.lock = threading.RLock()
        self._items: OrderedDict[str, Any] = OrderedDict()

    def get(self, key: str, loader: Callable[[], Any]) -> Any:
        with self.lock:
            if key in self._items:
                self._items.move_to_end(key)
                return self._items[key]
            item = loader()
            self._items[key] = item
            while len(self._items) > self.max_loaded:
                old_key, old = self._items.popitem(last=False)
                log.info("Unloading model %s to free memory", old_key)
                del old
                self._release()
            return item

    def loaded(self) -> list[str]:
        with self.lock:
            return list(self._items)

    @staticmethod
    def _release() -> None:
        gc.collect()
        torch = sys.modules.get("torch")
        if torch is not None and torch.cuda.is_available():
            torch.cuda.empty_cache()


GATED_HELP = (
    "This model is gated on Hugging Face. One-time fix: (1) create a free account at "
    "huggingface.co, (2) open https://huggingface.co/{model_id} while logged in and click "
    "'Agree and access repository', (3) run `lingua login` and paste a read token "
    "(huggingface.co/settings/tokens). Or set LB_TRANSLATION_ENGINE=nllb to skip IndicTrans2."
)


def _is_gated(exc: Exception) -> bool:
    text = f"{type(exc).__name__} {exc}".lower()
    return any(
        k in text
        for k in (
            "gatedrepo",
            "gated repo",
            "restricted",
            "401",
            "403",
            "log in",
            "access to model",
        )
    )


def load_error(model_id: str, exc: Exception) -> ModelUnavailableError:
    """Turn a loader failure into a message that says what to do next."""
    if _is_gated(exc):
        return ModelAccessError(f"No access to {model_id}. " + GATED_HELP.format(model_id=model_id))
    if type(exc).__name__ == "OutOfMemoryError":
        return ModelUnavailableError(
            f"Out of GPU memory loading {model_id}. Use LB_PROFILE=small, a smaller "
            "LB_MAX_LOADED_MODELS, or LB_DEVICE=cpu."
        )
    return ModelUnavailableError(
        f"Could not load model {model_id}: {type(exc).__name__}: {exc}. The first run downloads "
        "models from Hugging Face, so it needs internet access to huggingface.co (set "
        "HF_ENDPOINT if you use a mirror). `lingua doctor` checks this."
    )


def length_sorted_batches(texts: Sequence[str], size: int) -> Iterator[tuple[list[int], list[str]]]:
    """Yield (original indexes, texts) in batches of similar length: less padding, faster."""
    order = sorted(range(len(texts)), key=lambda i: len(texts[i]), reverse=True)
    for start in range(0, len(order), size):
        idx = order[start : start + size]
        yield idx, [texts[i] for i in idx]


def safe_generate(model: Any, inputs: Any, **kwargs: Any) -> Any:
    """model.generate with two guarded retries for known cross-version failures.

    * cache API mismatches in remote-code models (AttributeError/TypeError): retry without cache.
    * fp16 overflow ("nan"/"inf" probabilities): convert to float32 in place and retry.
    """
    torch = import_torch()
    with torch.inference_mode():
        try:
            return model.generate(**inputs, **kwargs)
        except (AttributeError, TypeError) as exc:
            log.warning("generate() failed (%s); retrying with use_cache=False", exc)
            return model.generate(**inputs, **{**kwargs, "use_cache": False})
        except RuntimeError as exc:
            msg = str(exc).lower()
            if ("nan" in msg or "inf" in msg) and next(model.parameters()).dtype != torch.float32:
                log.warning("Numeric overflow in half precision; switching model to float32")
                model.float()
                return model.generate(**inputs, **kwargs)
            raise
