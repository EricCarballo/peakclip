import json, re, threading, subprocess, time
from pathlib import Path
from datetime import datetime
from peakclip.domain.progress import telemetry
from peakclip.platforms import channel, kick
from peakclip.infrastructure.storage import (
    DEFAULT_OUTPUT,
    save_resume,
    load_resume,
    save_session,
    cleanup_workspace,
    temps_present,
)

from peakclip.application.clip_pipeline import ClipPipeline
from peakclip.infrastructure.video_processor import FFmpegVideoProcessor

DATA = DEFAULT_OUTPUT


class ClipJobs:
    def __init__(self, pipeline=None, video_processor=None):
        self.lock = threading.Lock()
        self.cancelled = threading.Event()
        self.peaks_choice = threading.Event()
        self.selected_peak_ids = None
        self.process = None
        self.state = {
            "busy": False,
            "message": "Pega un enlace para comenzar.",
            "clips": [],
            "logs": [],
            "output_error": False,
            "default_folder": str(DATA),
            "output_folder": None,
            "temps_available": False,
        }
        self.metadata = {}
        self.publish_lock = threading.Lock()
        self.state["social_status"] = {"busy": False, "message": ""}
        self.state.update(
            stage="idle",
            stage_progress=None,
            current=0,
            total=0,
            completed=0,
            events=[],
            speed="",
            eta="",
            started_at=None,
            resumable=False,
            awaiting_peaks=False,
            peaks_preview=[],
            chat_heatmap=[],
            rate_limited=False,
        )
        self.job = None
        self.pipeline = pipeline or ClipPipeline()
        self.video_processor = video_processor or FFmpegVideoProcessor(self.run)
        self.caption_service = None

    def default_folder(self):
        return str(DATA)

    def status(self):
        with self.lock:
            return json.loads(json.dumps(self.state))

    def update(self, **values):
        with self.lock:
            self.state.update(values)

    def inspect_link(self, value):
        try:
            result = channel.inspect(value)
            platform = (
                result.get("platform") or result["channel"].get("platform") or "twitch"
            )
            with self.lock:
                for video in result["videos"]:
                    self.metadata[video["id"]] = {
                        "channel": result["channel"]["login"],
                        "title": video["title"],
                        "platform": platform,
                        "source": video.get("source") or "",
                        "channel_id": video.get("channel_id")
                        or result["channel"].get("channel_id"),
                        "start_time": video.get("start_time")
                        or video.get("createdAt")
                        or "",
                        "duration": video.get("lengthSeconds") or 0,
                        "url": video.get("url") or "",
                        "is_live": bool(video.get("is_live")),
                    }
            return {"ok": True, **result}
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        except kick.KickError as e:
            return {"ok": False, "error": str(e)}
        except Exception:
            return {
                "ok": False,
                "error": "No pudimos consultar el canal. Comprueba tu conexión y vuelve a intentarlo.",
            }

    def cancel(self):
        self.cancelled.set()
        self.peaks_choice.set()
        self.update(
            message="Cancelando subtítulos…"
            if self.state.get("caption_job")
            else "Pausando. Guardamos el progreso para poder reanudar.",
            rate_limited=False,
        )
        if self.process and self.process.poll() is None:
            subprocess.run(
                ["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                creationflags=subprocess.CREATE_NO_WINDOW,
                capture_output=True,
            )

    def confirm_peaks(self, ids):
        """Resume clipping after the user reviews detected moments."""
        if not self.state.get("awaiting_peaks"):
            return {"ok": False, "error": "No hay momentos pendientes de confirmar."}
        try:
            chosen = sorted({int(value) for value in (ids or [])})
        except (TypeError, ValueError):
            return {"ok": False, "error": "La selección de momentos no es válida."}
        if not chosen:
            return {"ok": False, "error": "Elige al menos un momento para continuar."}
        self.selected_peak_ids = chosen
        with self.lock:
            self.state["busy"] = True
            self.state["awaiting_peaks"] = False
        self.update(
            message="Continuando con los momentos elegidos…",
            stage="download",
            started_at=time.time(),
        )
        self.peaks_choice.set()
        return {"ok": True}

    def phase(self, stage, message, **values):
        with self.lock:
            event = {
                "id": str(time.time_ns()),
                "time": datetime.now().strftime("%H:%M:%S"),
                "text": message,
            }
            self.state["events"] = (self.state["events"] + [event])[-12:]
            self.state.update(
                stage=stage,
                message=message,
                stage_progress=None,
                speed="",
                eta="",
                **values,
            )

    def public_error(self, exc):
        """Keep technical HTTP/network codes out of the main status line."""
        if isinstance(exc, kick.KickError):
            return str(exc)
        msg = str(exc or "").strip()
        low = msg.lower()
        if "429" in msg or "too many requests" in low:
            return "Kick está limitando las peticiones ahora mismo. Espera un minuto y vuelve a intentarlo."
        if re.search(r"http\s*error\s*\d+", low) or re.search(r"\b[45]\d{2}\b", msg):
            return "Kick no respondió bien. Espera un momento y vuelve a intentarlo."
        if (
            "timed out" in low
            or "urlopen" in low
            or "getaddrinfo" in low
            or "connection" in low
        ):
            return "No hay respuesta de la red. Comprueba tu conexión e inténtalo de nuevo."
        if msg and "traceback" not in low and len(msg) < 180:
            return msg
        return "Algo falló al procesar el directo. Inténtalo de nuevo."

    def run(self, args, stage=None, duration=0, cwd=None):
        if self.cancelled.is_set():
            raise RuntimeError("Proceso cancelado.")
        self.process = subprocess.Popen(
            args,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        for line in self.process.stdout:
            with self.lock:
                self.state["logs"] = (self.state["logs"] + [line.strip()])[-100:]
            if stage:
                values = telemetry(line.strip(), stage, duration)
                if values:
                    self.update(**values)
        code = self.process.wait()
        if self.cancelled.is_set():
            raise RuntimeError("Proceso cancelado.")
        if code:
            raise RuntimeError(
                "La herramienta no pudo completar la operación. Consulta los detalles; el vídeo puede no estar disponible."
            )

    def start(self, options):
        if self.state["busy"]:
            return False
        try:
            from peakclip.domain.captions import settings

            if options.get("captions"):
                options["caption_settings"] = settings(options.get("caption_settings"))
            platform, kind, vod = channel.parse_link(options["url"])
            if kind != "video":
                raise ValueError(
                    "Elige una grabación del canal antes de generar clips."
                )
            for key, lo, hi in [
                ("count", 1, 30),
                ("before", 0, 120),
                ("after", 1, 120),
            ]:
                if not lo <= int(options[key]) <= hi:
                    raise ValueError(f"El valor de {key} debe estar entre {lo} y {hi}.")
            if float(options["minimum"]) not in (1.5, 2, 3):
                raise ValueError("Selecciona una sensibilidad válida.")
            if options["folder"] and (
                not Path(options["folder"]).is_absolute() or "://" in options["folder"]
            ):
                raise ValueError(
                    "Elige una carpeta local válida para guardar los clips."
                )
            mode = str(options.get("folder_mode") or "stream")
            if mode not in ("stream", "custom"):
                raise ValueError("Elige cómo nombrar la carpeta del directo.")
            if mode == "custom" and not str(options.get("folder_name") or "").strip():
                raise ValueError(
                    "Escribe un nombre para la carpeta dentro del canal, o usa el título del directo."
                )
            if platform == "kick" and vod in self.metadata:
                meta = self.metadata.get(vod) or {}
                if meta.get("is_live"):
                    raise ValueError(
                        "Ese directo de Kick sigue en vivo. Espera a que termine para crear clips."
                    )
                if int(meta.get("duration") or 0) < 60:
                    raise ValueError(
                        "Elige un directo de Kick ya terminado. Los que siguen en vivo no sirven para clips."
                    )
        except (ValueError, KeyError, TypeError) as e:
            self.update(message=str(e))
            return False
        with self.lock:
            if self.state["busy"]:
                return False
            self.state["busy"] = True
        self.cancelled.clear()
        self.peaks_choice.clear()
        self.selected_peak_ids = None
        self.job = {
            "platform": platform,
            "vod": vod,
            "options": options.copy(),
            "resume": False,
        }
        self.update(
            clips=[],
            logs=[],
            events=[],
            output_error=False,
            output_folder=None,
            temps_available=False,
            resumable=False,
            awaiting_peaks=False,
            peaks_preview=[],
            chat_heatmap=[],
            rate_limited=False,
            stage="prepare",
            stage_progress=None,
            current=0,
            total=0,
            completed=0,
            speed="",
            eta="",
            started_at=time.time(),
            message="Comprobando la carpeta de destino…",
        )
        threading.Thread(
            target=self.work, args=(platform, vod, options.copy(), False), daemon=True
        ).start()
        return True

    def resume(self):
        if self.state.get("busy"):
            return False
        folder = getattr(self, "output", None)
        job = load_resume(folder) if folder else None
        if not job and self.job and self.job.get("options"):
            job = self.job
        if not job or not job.get("options") or not job.get("vod"):
            self.update(
                message="No hay un proceso para reanudar. Vuelve a crear los clips."
            )
            return False
        platform = job.get("platform") or "twitch"
        vod = job.get("vod")
        options = dict(job.get("options") or {})
        with self.lock:
            if self.state["busy"]:
                return False
            self.state["busy"] = True
        self.cancelled.clear()
        self.job = {
            **job,
            "resume": True,
            "platform": platform,
            "vod": vod,
            "options": options,
        }
        ready = [c for c in (self.state.get("clips") or []) if c.get("ready")]
        self.update(
            logs=[],
            events=[],
            output_error=False,
            resumable=False,
            stage="prepare",
            stage_progress=None,
            current=0,
            speed="",
            eta="",
            started_at=time.time(),
            message="Reanudando desde el último punto guardado…",
            clips=ready,
            completed=len(ready),
        )
        threading.Thread(
            target=self.work, args=(platform, vod, options, True), daemon=True
        ).start()
        return True

    def _write_job(
        self,
        output,
        platform,
        vod,
        o,
        metadata,
        stage,
        peaks=None,
        clips=None,
        chat_complete=False,
    ):
        serial_peaks = []
        for peak in peaks or []:
            serial_peaks.append(list(peak) if isinstance(peak, (tuple, list)) else peak)
        # Drop huge base64 thumbs from resume snapshots.
        serial_clips = []
        for clip in clips or []:
            if not clip.get("ready"):
                continue
            entry = {k: v for k, v in clip.items() if k != "thumbnail"}
            serial_clips.append(entry)
        payload = {
            "version": 1,
            "platform": platform,
            "vod": vod,
            "options": o,
            "metadata": metadata,
            "stage": stage,
            "chat_complete": bool(chat_complete),
            "peaks": serial_peaks,
            "clips": serial_clips,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        self.job = payload
        try:
            save_resume(output, payload)
        except OSError:
            pass

    def _mark_resumable(self, platform, vod, o, metadata, peaks, clips, chat_complete):
        folder = getattr(self, "output", None)
        if not folder or not o:
            return
        try:
            self._write_job(
                folder,
                platform,
                vod,
                o,
                metadata or {},
                "paused",
                peaks=peaks or [],
                clips=clips or [],
                chat_complete=chat_complete,
            )
            self.update(resumable=True)
        except Exception:
            pass

    def _persist_session(self, clips, metadata, output, vod=""):
        ready = [c for c in clips if c.get("ready") and c.get("path")]
        if not ready or not output:
            return
        try:
            save_session(
                output,
                ready,
                {
                    "channel": (metadata or {}).get("channel") or "",
                    "title": (metadata or {}).get("title") or "",
                    "folder_label": Path(output).name,
                    "platform": (metadata or {}).get("platform") or "twitch",
                    "vod": vod or (metadata or {}).get("vod") or "",
                },
            )
        except OSError:
            pass

    def cleanup_temps(self):
        if self.state.get("busy"):
            return {"ok": False, "error": "Espera a que termine el proceso."}
        folder = getattr(self, "output", None)
        if not folder or not Path(folder).is_dir():
            return {"ok": False, "error": "No hay una carpeta de clips para limpiar."}
        try:
            result = cleanup_workspace(folder)
        except Exception:
            return {
                "ok": False,
                "error": "No se pudieron eliminar los archivos temporales.",
            }
        still = temps_present(folder)
        self.update(temps_available=still)
        if result["already_clean"]:
            self.update(message="No quedaban chat ni archivos temporales.")
            return {"ok": True, **result}
        freed = result["bytes"] / 1048576
        note = f"Eliminados {result['removed']} archivos temporales"
        note += f" ({freed:.1f} MB)." if freed >= 0.1 else "."
        self.update(message=note + " Se conservaron los clips y sus textos.")
        return {"ok": True, **result}

    def work(self, platform, vod, options, resume=False):
        self.pipeline.execute(self, platform, vod, options, resume)
