import json
import sys
import tempfile
from pathlib import Path
from peakclip.infrastructure.storage import DEFAULT_OUTPUT


class FasterWhisperTranscriber:
    def __init__(self, runner):
        self.runner = runner

    def transcribe(self, source, duration, notify):
        notify(
            "transcribe",
            "Transcribiendo la voz. La primera vez se descarga el modelo; después funciona sin conexión.",
        )
        cache = DEFAULT_OUTPUT.parent / "models"
        cache.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="peakclip-transcribe-") as temp:
            target = Path(temp) / "transcript.json"
            command = (
                [sys.executable, "--transcribe-worker"]
                if getattr(sys, "frozen", False)
                else [sys.executable, "-m", "peakclip.infrastructure.whisper_worker"]
            )
            try:
                self.runner(
                    command + [str(source), str(target), str(cache), str(duration)],
                    stage="transcribe",
                )
            except RuntimeError as exc:
                if target.exists():
                    failure = json.loads(target.read_text(encoding="utf-8"))
                    if failure.get("error"):
                        raise RuntimeError(
                            "No se pudo transcribir: " + failure["error"][:120]
                        ) from exc
                raise RuntimeError(
                    "No se pudo transcribir. Revisa la conexión para descargar el modelo o consulta el registro. El clip se conserva."
                ) from exc
            return json.loads(target.read_text(encoding="utf-8"))
