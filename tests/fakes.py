"""Fake translators: the router, engine, API and CLI are tested without loading any model."""

from __future__ import annotations

from collections.abc import Sequence


class FakeTranslator:
    """Tags each segment with the hop that handled it, so tests can read the route from the text."""

    def __init__(self, name: str, pairs: set[tuple[str, str]] | None = None, *, zh_only: bool = False,
                 error: Exception | None = None) -> None:  # fmt: skip
        self.name, self.pairs, self.zh_only, self.error = name, pairs, zh_only, error
        self.calls: list[tuple[str, str, list[str]]] = []

    def supports(self, src: str, tgt: str) -> bool:
        if src == tgt:
            return False
        if self.zh_only:
            return "zh" in (src, tgt)
        return self.pairs is None or (src, tgt) in self.pairs

    def model_id(self, src: str, tgt: str) -> str:
        return f"fake/{self.name}"

    def translate(self, texts: Sequence[str], src: str, tgt: str) -> list[str]:
        self.calls.append((src, tgt, list(texts)))
        if self.error:
            raise self.error
        return [f"[{src}>{tgt}:{self.name}] {t}" for t in texts]


INDIC_PAIRS = {(a, b) for a in ("sa", "hi", "en") for b in ("sa", "hi", "en") if a != b}


def make_backends(**kwargs: FakeTranslator) -> dict[str, FakeTranslator]:
    backends = {
        "indictrans2": FakeTranslator("it2", INDIC_PAIRS),
        "zh": FakeTranslator("zh", zh_only=True),
        "nllb": FakeTranslator("nllb"),
    }
    backends.update(kwargs)
    return backends
