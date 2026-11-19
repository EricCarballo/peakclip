"""Small replaceable boundaries for caption use cases."""

from pathlib import Path
from typing import Callable, Protocol


class Transcriber(Protocol):
    def transcribe(self, source: Path, duration: float, notify: Callable) -> dict: ...


class CaptionRepository(Protocol):
    def load(self, source: Path) -> dict | None: ...
    def save(self, source: Path, document: dict) -> None: ...


class CaptionRenderer(Protocol):
    def render(
        self, source: Path, document: dict, duration: float, preview: bool = False
    ) -> Path: ...
