"""Locate ffmpeg / yt-dlp / TwitchDownloaderCLI for portable and dev runs."""
from __future__ import annotations
import os
import sys
from pathlib import Path

from peakclip.infrastructure.paths import project_root


def tool_search_dirs():
    dirs = []
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
        dirs.extend([base / "tools", base])
    else:
        dirs.append(project_root() / "tools")
    dirs.append(Path.home() / "AppData/Local/Programs/Python/Python313/Scripts")
    return dirs


def ensure_tools_on_path():
    current = os.environ.get("PATH", "")
    prepend = []
    for folder in tool_search_dirs():
        if folder.is_dir() and str(folder) not in current and str(folder) not in prepend:
            prepend.append(str(folder))
    if prepend:
        os.environ["PATH"] = os.pathsep.join(prepend + [current]) if current else os.pathsep.join(prepend)
