"""Logging setup shared by the CLI and the API. The route log is the one to watch."""

from __future__ import annotations

import logging


def setup_logging(level: str = "INFO") -> None:
    root = logging.getLogger("lingua_bridge")
    root.setLevel(level.upper())
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", "%H:%M:%S")
        )
        root.addHandler(handler)
        root.propagate = False
