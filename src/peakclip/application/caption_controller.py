"""Background caption commands. The shared job gate prevents index/session races."""

import threading
import time
import traceback
from pathlib import Path
from peakclip.domain.captions import catalog, settings
from peakclip.infrastructure.video_processor import media_duration


class CaptionController:
    def __init__(self, jobs, service, repository, media):
        self.jobs, self.service, self.repository, self.media = (
            jobs,
            service,
            repository,
            media,
        )
        jobs.update(caption_status={"busy": False, "message": "", "revision": 0})

    def clip(self, index):
        clip = self.jobs.status()["clips"][int(index)]
        if not clip.get("ready") or not Path(clip["path"]).is_file():
            raise ValueError("Primero genera el vídeo de este clip.")
        clip["duration"] = media_duration(clip["path"])
        return clip

    def caption_catalog(self):
        return catalog()

    def caption_open(self, index):
        try:
            clip = self.clip(index)
            return {
                "ok": True,
                "document": self.repository.load(Path(clip["path"])),
                "url": self.media.url(clip["path"]),
                "duration": clip["duration"],
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def caption_media(self, index, rendered=False):
        try:
            clip = self.clip(index)
            path = clip.get("caption_path") if rendered else clip["path"]
            return {"ok": True, "url": self.media.url(path or clip["path"])}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def caption_save(self, index, document):
        if self.jobs.status()["busy"]:
            return {"ok": False, "error": "Espera a que termine el proceso actual."}
        try:
            clip = self.clip(index)
            doc = self.service.save(clip["path"], clip["duration"], document)
            return {"ok": True, "document": doc}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _start(self, index, operation):
        with self.jobs.lock:
            if self.jobs.state["busy"]:
                return {"ok": False, "error": "Espera a que termine el proceso actual."}
            self.jobs.state["busy"] = True
        self.jobs.cancelled.clear()
        self.jobs.update(
            caption_status={
                "busy": True,
                "index": int(index),
                "message": "Preparando subtítulos…",
                "revision": time.time_ns(),
            },
            resumable=False,
            caption_job=True,
            started_at=time.time(),
            events=[],
        )

        def work():
            try:
                clip = self.clip(index)
                result = operation(clip)
                message = result.pop(
                    "message",
                    "Subtítulos listos. Revisa las palabras antes de compartir.",
                )
                self.jobs.phase("done", message)
                self.jobs.update(
                    caption_status={
                        "busy": False,
                        "index": int(index),
                        "message": message,
                        "revision": time.time_ns(),
                        **result,
                    }
                )
            except Exception as exc:
                cancelled = self.jobs.cancelled.is_set()
                message = (
                    "Operación cancelada. El vídeo original y el texto guardado se conservaron."
                    if cancelled
                    else self.jobs.public_error(exc)
                )
                self.jobs.phase(
                    "cancelled" if cancelled else "error", message, resumable=False
                )
                self.jobs.update(
                    caption_status={
                        "busy": False,
                        "index": int(index),
                        "error": message,
                        "message": message,
                        "revision": time.time_ns(),
                    },
                    logs=self.jobs.status()["logs"] + [traceback.format_exc()],
                )
            finally:
                self.jobs.update(busy=False, caption_job=False)

        threading.Thread(target=work, daemon=True).start()
        return {"ok": True}

    def caption_transcribe(self, index, options=None):
        try:
            options = settings(options)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

        def transcribe(clip):
            doc = self.service.prepare(
                clip["path"], clip["duration"], options, self.jobs.phase
            )
            return {
                "document": doc,
                "message": "Texto preparado. Puedes corregirlo y elegir su estilo."
                if doc["cues"]
                else "No detectamos voz. Puedes añadir frases manualmente.",
            }

        return self._start(index, transcribe)

    def caption_export(self, index, document, preview=False):
        def export(clip):
            self.jobs.phase(
                "caption_render",
                "Renderizando una muestra de 8 segundos…"
                if preview
                else "Exportando el vídeo con subtítulos…",
            )
            path = self.service.export(
                clip["path"], clip["duration"], document, preview
            )
            if not preview:
                with self.jobs.lock:
                    self.jobs.state["clips"][int(index)]["caption_path"] = str(path)
                state = self.jobs.status()
                self.jobs._persist_session(
                    state["clips"],
                    {
                        "channel": state.get("channel"),
                        "title": state.get("video_title"),
                        "platform": state.get("platform"),
                    },
                    path.parent,
                )
            return {
                "url": self.media.url(path),
                "preview": preview,
                "path": str(path),
                "message": "Muestra renderizada: así se verá la exportación."
                if preview
                else "Versión subtitulada guardada. «Ver clip» y compartir usarán esta versión.",
            }

        return self._start(index, export)
