import shutil, base64, traceback
from datetime import datetime
from peakclip.domain import chat_analysis as engine
from peakclip.platforms import channel, kick
from peakclip.infrastructure.storage import (
    OutputError,
    prepare_output,
    session_directory,
    file_stamp,
    cleanup_workspace,
    temps_present,
    load_resume,
    clear_resume,
    chat_progress_file,
)
from peakclip.infrastructure.tools import ensure_tools_on_path
from peakclip.social import drafts as social


class ClipPipeline:
    def execute(self, jobs, platform, vod, o, resume=False):
        metadata = {}
        peaks = []
        clips = []
        chat_complete = False
        try:
            jobs.phase(
                "prepare",
                "Reanudando el proceso."
                if resume
                else "Preparando el directo y su carpeta.",
            )
            with jobs.lock:
                metadata = jobs.metadata.get(vod)
            saved = None
            if resume:
                saved = (
                    load_resume(getattr(jobs, "output", None))
                    if getattr(jobs, "output", None)
                    else None
                )
                if not saved and jobs.job:
                    saved = jobs.job
                if saved and saved.get("metadata"):
                    metadata = saved.get("metadata") or metadata
            if metadata is None:
                info = (
                    kick.inspect(vod)
                    if platform == "kick"
                    else channel.inspect(f"https://www.twitch.tv/videos/{vod}")
                )
                video = info["videos"][0]
                metadata = {
                    "channel": info["channel"]["login"],
                    "title": video["title"],
                    "platform": platform,
                    "source": video.get("source") or "",
                    "channel_id": video.get("channel_id")
                    or info["channel"].get("channel_id"),
                    "start_time": video.get("start_time")
                    or video.get("createdAt")
                    or "",
                    "duration": video.get("lengthSeconds") or 0,
                    "url": video.get("url") or "",
                    "is_live": bool(video.get("is_live")),
                }
            platform = metadata.get("platform") or platform
            if platform == "kick":
                if metadata.get("is_live"):
                    raise RuntimeError(
                        "Ese directo de Kick sigue en vivo. Espera a que termine para crear clips."
                    )
                if int(metadata.get("duration") or 0) < 60:
                    raise RuntimeError(
                        "Elige un directo de Kick ya terminado. Los que siguen en vivo no sirven para clips."
                    )
            label = (
                (o.get("folder_name") or "").strip()
                if o.get("folder_mode") == "custom"
                else ""
            )
            output = prepare_output(
                o["folder"],
                vod,
                metadata["channel"],
                metadata["title"],
                folder_label=label,
                platform=platform,
            )
            jobs.output = output
            if resume:
                saved = load_resume(output) or saved or {}
            else:
                clear_resume(output)
                saved = {}
            session = session_directory(output)
            jobs.update(
                output_folder=str(output),
                channel=metadata["channel"],
                video_title=metadata["title"],
                folder_label=output.name,
                temps_available=True,
                platform=platform,
                from_history=False,
                resumable=False,
            )
            ensure_tools_on_path()
            needed = (["yt-dlp", "ffmpeg"] if o["cut"] else []) + (
                [] if platform == "kick" else ["TwitchDownloaderCLI"]
            )
            for tool in needed:
                if not shutil.which(tool):
                    raise RuntimeError(
                        f"Falta {tool}. En la versión portable debe estar en la carpeta tools junto a Peak Clip.exe."
                    )
            chat = session / "chat.json"
            chat_checkpoint = chat_progress_file(output)
            chat_complete = bool(saved.get("chat_complete"))
            if chat_complete and not chat.exists():
                prior = kick.load_chat_progress(chat_checkpoint)
                if (
                    prior
                    and prior.get("complete")
                    and prior.get("comments") is not None
                ):
                    kick.write_chat_file(
                        chat,
                        metadata.get("channel_id") or prior.get("channel_id"),
                        prior.get("comments") or [],
                    )
            if not chat_complete or not chat.exists():
                jobs.phase(
                    "chat",
                    "Reanudando la descarga del chat."
                    if resume and chat_checkpoint.exists()
                    else "Descargando el chat del directo.",
                )
                jobs._write_job(
                    output,
                    platform,
                    vod,
                    o,
                    metadata,
                    "chat",
                    peaks=saved.get("peaks") or [],
                    clips=saved.get("clips") or [],
                    chat_complete=False,
                )
                if platform == "kick":

                    def chat_progress(count, pages, note=None):
                        if note:
                            jobs.update(message=note)
                        else:
                            jobs.update(
                                message=f"Descargando chat de Kick… {count:,} mensajes ({pages} páginas)"
                            )

                    kick.download_chat(
                        metadata.get("channel_id"),
                        metadata.get("start_time"),
                        metadata.get("duration") or 0,
                        chat,
                        progress=chat_progress,
                        cancelled=jobs.cancelled.is_set,
                        checkpoint=chat_checkpoint,
                    )
                else:
                    jobs.run(
                        [
                            "TwitchDownloaderCLI",
                            "chatdownload",
                            "--id",
                            vod,
                            "-o",
                            str(chat),
                        ],
                        stage="chat",
                    )
                chat_complete = True
            else:
                jobs.phase("chat", "Chat ya descargado. Continuamos.")
            jobs._write_job(
                output,
                platform,
                vod,
                o,
                metadata,
                "analyze",
                peaks=saved.get("peaks") or [],
                clips=saved.get("clips") or [],
                chat_complete=True,
            )
            jobs.phase("analyze", "Buscando las reacciones más fuertes del chat.")
            messages, _ = engine.leer_chat(chat)
            if not messages:
                raise RuntimeError("El chat está vacío. Prueba otro directo.")
            peaks = saved.get("peaks") if resume and saved.get("peaks") else None
            if not peaks:
                peaks = engine.buscar_picos(
                    engine.contar(messages, 10),
                    10,
                    int(o["count"]),
                    90,
                    float(o["minimum"]),
                )
            jobs.update(total=len(peaks))
            if peaks:
                jobs.phase(
                    "analyze",
                    f"{len(peaks)} momentos encontrados en {len(messages):,} mensajes.",
                )
            jobs._write_job(
                output,
                platform,
                vod,
                o,
                metadata,
                "clips",
                peaks=peaks,
                clips=saved.get("clips") or [],
                chat_complete=True,
            )
            media = (
                metadata.get("source")
                if platform == "kick"
                else f"https://www.twitch.tv/videos/{vod}"
            )
            if platform == "kick" and not media:
                raise RuntimeError(
                    "Kick no devolvió la fuente de vídeo de esta grabación."
                )
            clips = list(saved.get("clips") or []) if resume else []
            if resume and not clips:
                with jobs.lock:
                    clips = [
                        c for c in (jobs.state.get("clips") or []) if c.get("ready")
                    ]
            done_numbers = {
                int(c.get("number"))
                for c in clips
                if c.get("ready") and c.get("number") is not None
            }
            jobs.update(
                clips=list(clips), completed=len(done_numbers), total=len(peaks)
            )
            for n, (strength, i, _, __) in enumerate(peaks, 1):
                if jobs.cancelled.is_set():
                    raise RuntimeError("Proceso cancelado.")
                if n in done_numbers:
                    continue
                start = max(0, i * 10 - int(o["before"]))
                end = i * 10 + 10 + int(o["after"])
                moment = metadata.get("url") or (
                    f"https://kick.com/{metadata['channel']}/videos/{vod}"
                    if platform == "kick"
                    else f"https://www.twitch.tv/videos/{vod}?t={i * 10}s"
                )
                if platform == "twitch":
                    moment = f"https://www.twitch.tv/videos/{vod}?t={i * 10}s"
                item = {
                    "number": n,
                    "time": engine.hms(start),
                    "end": engine.hms(end),
                    "duration": end - start,
                    "strength": round(strength, 1),
                    "url": moment,
                    "ready": False,
                    "video_title": metadata["title"],
                    "channel": metadata["channel"],
                    "platform": platform,
                }
                item["social"] = social.suggest(
                    metadata["title"],
                    metadata["channel"],
                    messages,
                    start,
                    end,
                    platform_source=platform,
                )
                if o["cut"]:
                    jobs.phase(
                        "download",
                        f"Descargando el fragmento {n} de {len(peaks)}.",
                        current=n,
                    )
                    raw = session / f"fragmento_{n}.mp4"
                    dest = jobs.output / f"clip{n}_{file_stamp()}.mp4"
                    jobs.run(
                        [
                            "yt-dlp",
                            "--newline",
                            "--no-playlist",
                            "-f",
                            "best[height<=1080]/best",
                            "--download-sections",
                            f"*{start}-{end}",
                            "--force-keyframes-at-cuts",
                            "-o",
                            str(raw),
                            media,
                        ],
                        stage="download",
                    )
                    jobs.phase(
                        "encode",
                        f"Convirtiendo clip {n} a formato vertical 1080 × 1920.",
                    )
                    try:
                        jobs.video_processor.vertical(raw, dest, end - start)
                    except Exception:
                        if dest.exists():
                            dest.rename(session / (dest.name + ".incompleto"))
                        raise
                    jobs.phase("thumbnail", f"Preparando la vista previa del clip {n}.")
                    thumb = session / f"preview_{n}.jpg"
                    try:
                        jobs.video_processor.thumbnail(raw, thumb)
                        lasting = dest.with_suffix(".jpg")
                        shutil.copy2(thumb, lasting)
                        item["thumbnail_file"] = str(lasting)
                        item["thumbnail"] = (
                            "data:image/jpeg;base64,"
                            + base64.b64encode(lasting.read_bytes()).decode()
                        )
                    except Exception:
                        pass
                    raw.unlink(missing_ok=True)
                    item.update(
                        ready=True,
                        path=str(dest),
                        filename=dest.name,
                        created_at=datetime.now().isoformat(timespec="seconds"),
                        size_bytes=dest.stat().st_size,
                    )
                    try:
                        social.save(dest, item["social"])
                    except OSError:
                        jobs.phase(
                            "saved",
                            "Clip guardado; no se pudieron guardar sus textos. Puedes reintentarlo desde Compartir.",
                        )
                    jobs.phase(
                        "saved",
                        f"Clip {n} guardado. {engine.hms(start)} a {engine.hms(end)}.",
                    )
                clips.append(item)
                jobs.update(clips=list(clips))
                if o["cut"] and o.get("captions") and jobs.caption_service:
                    jobs._persist_session(clips, metadata, output, vod)
                    try:
                        document = jobs.caption_service.prepare(
                            dest,
                            item["duration"],
                            o.get("caption_settings"),
                            jobs.phase,
                        )
                        if document["cues"]:
                            jobs.phase(
                                "caption_render", f"Añadiendo subtítulos al clip {n}."
                            )
                            rendered = jobs.caption_service.export(
                                dest, item["duration"], document
                            )
                            item["caption_path"] = str(rendered)
                        else:
                            jobs.phase(
                                "saved",
                                f"Clip {n}: no detectamos voz. Puedes añadir texto desde el editor.",
                            )
                    except Exception:
                        if jobs.cancelled.is_set():
                            raise
                        jobs.update(
                            logs=jobs.status()["logs"] + [traceback.format_exc()]
                        )
                        jobs.phase(
                            "saved",
                            f"Clip {n} guardado sin subtítulos. Puedes reintentar desde «Añadir subtítulos».",
                        )
                    jobs.update(clips=list(clips))
                jobs.update(
                    completed=len([c for c in clips if c.get("ready") or not o["cut"]])
                )
                jobs._write_job(
                    output,
                    platform,
                    vod,
                    o,
                    metadata,
                    "clips",
                    peaks=peaks,
                    clips=clips,
                    chat_complete=True,
                )
                if o["cut"]:
                    jobs._persist_session(clips, metadata, output, vod)
            if jobs.cancelled.is_set():
                raise RuntimeError(
                    "Proceso cancelado. Los clips terminados se conservaron."
                )
            result_word = (
                ("clip guardado." if len(clips) == 1 else "clips guardados.")
                if o["cut"]
                else (
                    "momento encontrado."
                    if len(clips) == 1
                    else "momentos encontrados."
                )
            )
            message = (
                f"Listo. {len(clips)} {result_word}"
                if clips
                else "No encontramos picos claros. Prueba una sensibilidad más amplia."
            )
            if o.get("captions") and o["cut"] and clips:
                subtitled = sum(bool(c.get("caption_path")) for c in clips)
                message += f" {subtitled} con subtítulos."
                if subtitled < len(clips):
                    message += " Revisa los restantes desde «Añadir subtítulos»."
            if o.get("cleanup_temps") and temps_present(output):
                cleaned = cleanup_workspace(output)
                if cleaned["removed"]:
                    freed = cleaned["bytes"] / 1048576
                    message += (
                        f" Chat y temporales eliminados ({cleaned['removed']} archivos"
                    )
                    message += f", {freed:.1f} MB)." if freed >= 0.1 else ")."
            if o["cut"]:
                jobs._persist_session(clips, metadata, output, vod)
            clear_resume(output)
            jobs.job = None
            jobs.phase("done", message, resumable=False)
        except OutputError as e:
            jobs._mark_resumable(
                platform, vod, o, metadata, peaks, clips, chat_complete
            )
            jobs.phase(
                "error",
                jobs.public_error(e),
                output_error=True,
                logs=[traceback.format_exc()],
                resumable=True,
            )
        except Exception as e:
            try:
                folder = getattr(jobs, "output", None)
                with jobs.lock:
                    current = list(jobs.state.get("clips") or [])
                if folder and current:
                    jobs._persist_session(current, metadata or {}, folder, vod)
            except Exception:
                pass
            jobs._mark_resumable(
                platform, vod, o, metadata, peaks, clips, chat_complete
            )
            if jobs.cancelled.is_set():
                message = (
                    "Proceso pausado. Pulsa Reanudar para continuar donde lo dejaste."
                )
                if clips:
                    message = "Proceso pausado. Los clips listos se conservaron. Pulsa Reanudar para seguir."
                jobs.phase(
                    "cancelled",
                    message,
                    logs=jobs.status()["logs"] + [traceback.format_exc()],
                    resumable=True,
                )
            else:
                jobs.phase(
                    "error",
                    jobs.public_error(e)
                    + " Puedes pulsar Reanudar para no empezar de cero.",
                    logs=jobs.status()["logs"] + [traceback.format_exc()],
                    resumable=True,
                )
        finally:
            folder = getattr(jobs, "output", None)
            jobs.update(
                busy=False, temps_available=bool(folder and temps_present(folder))
            )
