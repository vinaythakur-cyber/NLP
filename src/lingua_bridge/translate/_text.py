"""Sentence segmentation. Models are trained on sentences, so long inputs are split first."""

from __future__ import annotations

import re

_NEWLINES = re.compile(r"(\n+)")
# Split after sentence enders followed by whitespace; Chinese enders need no whitespace.
_SENT = re.compile(r"(?<=[.!?।॥])\s+|(?<=[。！？])")
_MAX_CHARS = 400


def _chunk(segment: str) -> list[str]:
    """Break an over-long segment at the last space/comma before the limit."""
    parts: list[str] = []
    while len(segment) > _MAX_CHARS:
        cut = max(segment.rfind(sep, 0, _MAX_CHARS) for sep in (", ", "; ", "、", "，", " "))
        cut = cut + 1 if cut > 40 else _MAX_CHARS
        parts.append(segment[:cut].strip())
        segment = segment[cut:].strip()
    if segment:
        parts.append(segment)
    return parts


def split_text(text: str) -> tuple[list[str], list[str | int]]:
    """Return (segments to translate, layout). Layout holds segment indexes and literal separators."""
    segments: list[str] = []
    layout: list[str | int] = []
    for piece in _NEWLINES.split(text.strip()):
        if not piece:
            continue
        if piece.startswith("\n"):
            layout.append(piece)
            continue
        first = True
        for sentence in _SENT.split(piece):
            for chunk in _chunk(sentence.strip()):
                if not first:
                    layout.append(" ")
                layout.append(len(segments))
                segments.append(chunk)
                first = False
    return segments, layout


def join_text(translated: list[str], layout: list[str | int], tgt: str) -> str:
    """Reassemble translated segments. Chinese is written without spaces between sentences."""
    out = []
    for item in layout:
        if isinstance(item, int):
            out.append(translated[item])
        else:
            out.append("" if (tgt == "zh" and item == " ") else item)
    return "".join(out)
