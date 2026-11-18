"""Project / runtime path helpers."""
from __future__ import annotations
import sys
from pathlib import Path


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def ui_index() -> Path:
    return project_root() / "ui" / "index.html"
