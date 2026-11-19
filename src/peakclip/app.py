"""Desktop window bootstrap (pywebview)."""
from __future__ import annotations
import ctypes
from pathlib import Path

import webview

import peakclip.api as api_module
from peakclip.api import API
from peakclip.infrastructure.paths import bundle_root, ui_index
from peakclip.infrastructure.tools import ensure_tools_on_path


def run():
    ensure_tools_on_path()
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("PeakClip.Desktop")
    api = API()
    index = ui_index()
    if not index.is_file():
        raise SystemExit(f"No está la interfaz compilada en {index}. Ejecuta: npm run build")
    window = webview.create_window(
        "Peak Clip",
        index.as_uri(),
        js_api=api,
        width=1180,
        height=820,
        min_size=(820, 650),
    )
    api_module.window = window
    window.events.closing += lambda: api.cancel()
    window.events.closed += lambda: api._media.close()

    def maximize_on_ready():
        try:
            window.maximize()
        except Exception:
            pass

    window.events.shown += maximize_on_ready
    icon = bundle_root() / "assets" / "peak-clip.ico"
    webview.start(icon=str(icon) if icon.is_file() else None)


if __name__ == "__main__":
    run()
