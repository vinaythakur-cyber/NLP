"""Picks a backend per language pair: one direct hop, or a pivot through English.

Every translation reports the route it took, and every route is logged, so you can always
see when a pivot happened. A pivot means two models in a row: the second one translates
text the first one already got a little wrong, so errors compound.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal

from ..errors import ModelAccessError, UnsupportedPairError
from ..schemas import Hop
from .base import Translator

route_log = logging.getLogger("lingua_bridge.route")

# Specialist first: IndicTrans2 for anything within sa/hi/en, then the Chinese-pair backend.
BACKEND_PREFERENCE = ("indictrans2", "zh", "nllb")
# Hypothesis, not a measured result: NLLB's Sanskrit is thin, so Sanskrit<->Chinese goes
# through English (IndicTrans2 handles the Sanskrit hop). Override with LB_ROUTE_OVERRIDES
# and compare with eval/run_eval.py --compare.
PIVOT_BY_DEFAULT = {("sa", "zh"), ("zh", "sa")}
PIVOT_LANG = "en"

Via = Literal["direct", "pivot", "identity"]


@dataclass(frozen=True)
class HopPlan:
    src: str
    tgt: str
    backend: str


@dataclass
class RouteResult:
    texts: list[str]
    hops: list[Hop]
    via: Via
    warnings: list[str] = field(default_factory=list)


class Router:
    def __init__(
        self,
        backends: Mapping[str, Translator],
        overrides: Mapping[str, str] | None = None,
        *,
        preference: Sequence[str] = BACKEND_PREFERENCE,
        pivot_by_default: bool = True,
        fallback_to_nllb: bool = True,
    ) -> None:
        self.backends = dict(backends)
        self.overrides = dict(overrides or {})
        self.preference = tuple(preference)
        self.pivot_by_default = pivot_by_default
        self.fallback_to_nllb = fallback_to_nllb

    # ------------------------------------------------------------ planning

    def _default_backend(self, src: str, tgt: str) -> str | None:
        for name in self.preference:
            backend = self.backends.get(name)
            if backend is not None and backend.supports(src, tgt):
                return name
        return None

    def _hop(self, src: str, tgt: str, backend: str | None = None) -> HopPlan:
        name = backend or self._default_backend(src, tgt)
        if name is None:
            raise UnsupportedPairError(f"No translation model is available for {src}->{tgt}.")
        translator = self.backends.get(name)
        if translator is None or not translator.supports(src, tgt):
            raise UnsupportedPairError(f"Backend {name!r} cannot translate {src}->{tgt}.")
        return HopPlan(src, tgt, name)

    def _pivot(self, src: str, tgt: str) -> list[HopPlan]:
        if PIVOT_LANG in (src, tgt):
            raise UnsupportedPairError(f"Cannot pivot {src}->{tgt} through English.")
        return [self._hop(src, PIVOT_LANG), self._hop(PIVOT_LANG, tgt)]

    def plan(self, src: str, tgt: str) -> list[HopPlan]:
        if src == tgt:
            return []
        override = self.overrides.get(f"{src}>{tgt}")
        if override == "pivot":
            return self._pivot(src, tgt)
        if override == "direct":
            return [self._hop(src, tgt)]
        if override:
            return [self._hop(src, tgt, backend=override)]
        if self.pivot_by_default and (src, tgt) in PIVOT_BY_DEFAULT:
            return self._pivot(src, tgt)
        return [self._hop(src, tgt)]

    # ----------------------------------------------------------- execution

    def _run_hop(
        self, step: HopPlan, texts: list[str], warnings: list[str]
    ) -> tuple[list[str], str]:
        """Run one hop. If its model is gated and unavailable, fall back to NLLB with a warning."""
        backend = self.backends[step.backend]
        try:
            return backend.translate(texts, step.src, step.tgt), step.backend
        except ModelAccessError as exc:
            alt = self.backends.get("nllb")
            if not (self.fallback_to_nllb and alt is not None and step.backend != "nllb"
                    and alt.supports(step.src, step.tgt)):  # fmt: skip
                raise
            msg = (f"{step.backend} model for {step.src}->{step.tgt} is gated and you are not logged in "
                   "to Hugging Face, so NLLB was used instead (lower quality, especially for Sanskrit). "
                   "Run `lingua login` after accepting the model terms to enable IndicTrans2.")  # fmt: skip
            route_log.warning("%s (%s)", msg, exc)
            if msg not in warnings:
                warnings.append(msg)
            return alt.translate(texts, step.src, step.tgt), "nllb"

    def translate(self, segments: Sequence[str], src: str, tgt: str) -> RouteResult:
        plan = self.plan(src, tgt)
        if not plan:
            return RouteResult(list(segments), [], "identity")
        via: Via = "direct" if len(plan) == 1 else "pivot"
        texts = list(segments)
        hops: list[Hop] = []
        warnings: list[str] = []
        t_all = time.perf_counter()
        for step in plan:
            t0 = time.perf_counter()
            texts, used = self._run_hop(step, texts, warnings)
            hops.append(
                Hop(
                    src=step.src,
                    tgt=step.tgt,
                    backend=used,
                    model=self.backends[used].model_id(step.src, step.tgt),
                    ms=round((time.perf_counter() - t0) * 1000, 1),
                    segments=len(texts),
                )  # fmt: skip
            )
        route_log.info(
            "route %s->%s via=%s%s hops=[%s] ms=%.0f",
            src, tgt, via, " (PIVOT through English: errors can compound)" if via == "pivot" else "",
            ", ".join(f"{h.src}->{h.tgt}:{h.backend}/{h.model}" for h in hops),
            (time.perf_counter() - t_all) * 1000,
        )  # fmt: skip
        return RouteResult(texts, hops, via, warnings)
