"""Transcribe once, edit repeatedly, render without changing the source."""

from pathlib import Path
from peakclip.application.ports import CaptionRepository, CaptionRenderer, Transcriber
from peakclip.domain.captions import validate_document, settings


class CaptionService:
    def __init__(
        self,
        transcriber: Transcriber,
        repository: CaptionRepository,
        renderer: CaptionRenderer,
    ):
        self.transcriber, self.repository, self.renderer = (
            transcriber,
            repository,
            renderer,
        )

    def prepare(self, source, duration, options, notify):
        source = Path(source)
        document = self.repository.load(source)
        if document is None:
            document = self.transcriber.transcribe(source, duration, notify)
        document["settings"] = settings(options)
        return self.save(source, duration, document)

    def save(self, source, duration, document):
        result = validate_document(document, duration)
        self.repository.save(Path(source), result)
        return result

    def export(self, source, duration, document, preview=False):
        document = self.save(source, duration, document)
        if not document["cues"]:
            raise ValueError("No hay voz detectada. Añade una frase antes de exportar.")
        return self.renderer.render(Path(source), document, duration, preview)
