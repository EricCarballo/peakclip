"""Project / runtime path helpers."""
from __future__ import annotations
import sys
from pathlib import Path


def project_root() -> Path:
    """Repo / install folder (exe directory when frozen)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def bundle_root() -> Path:
    """PyInstaller data dir (_internal / _MEIPASS), or project root in dev."""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return project_root()


def ui_index() -> Path:
    return bundle_root() / "ui" / "index.html"
