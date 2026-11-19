import json, threading
from pathlib import Path
from datetime import datetime
import webview
from peakclip.social import drafts as social
from peakclip.social import youtube as youtube_share


class SocialController:
    def __init__(self, jobs, window_provider):
        self.jobs = jobs
        self.window_provider = window_provider

    def social_draft(self, index):
        clip = self.jobs.status()["clips"][int(index)]
        source = clip.get("platform") or "twitch"
        data = clip.get("social") or social.suggest(
            clip.get("video_title", ""),
            clip.get("channel", ""),
            [],
            0,
            0,
            platform_source=source,
        )
        data = social.ensure_platforms(
            data,
            clip.get("video_title", ""),
            clip.get("channel", ""),
            platform_source=source,
        )
        with self.jobs.lock:
            self.jobs.state["clips"][int(index)]["social"] = data
        return data

    def save_social(self, index, drafts):
        try:
            clip = self.jobs.status()["clips"][int(index)]
            source = clip.get("platform") or "twitch"
            data = social.ensure_platforms(
                clip.get("social") or {"basis": {}},
                clip.get("video_title", ""),
                clip.get("channel", ""),
                platform_source=source,
            )
            data["platforms"] = social.validate(drafts)
            if clip.get("ready"):
                social.save(clip["path"], data)
            with self.jobs.lock:
                self.jobs.state["clips"][int(index)]["social"] = data
            return {"ok": True}
        except Exception:
            return {
                "ok": False,
                "error": "No se pudieron guardar los textos. Comprueba la carpeta e inténtalo de nuevo.",
            }

    def social_accounts(self):
        return {
            "youtube": youtube_share.account(),
            "tiktok": {"connected": False},
            "instagram": {"connected": False},
            "facebook": {"connected": False},
        }

    def connect_youtube(self):
        if not self.jobs.publish_lock.acquire(blocking=False):
            return False
        try:
            path = self.window_provider().create_file_dialog(
                webview.FileDialog.OPEN, file_types=("Credenciales Google (*.json)",)
            )
        except Exception:
            self.jobs.publish_lock.release()
            return False
        if not path:
            self.jobs.publish_lock.release()
            return False
        self.jobs.update(
            social_status={
                "busy": True,
                "message": "Autoriza tu canal en la ventana de Google. El enlace caduca en 3 minutos.",
            }
        )

        def connect():
            try:
                result = youtube_share.connect(path[0])
                self.jobs.update(
                    social_status={
                        "busy": False,
                        "message": "Conectado: " + result["name"],
                    }
                )
            except Exception:
                self.jobs.update(
                    social_status={
                        "busy": False,
                        "message": "No se pudo conectar. Usa un JSON OAuth de escritorio, habilita YouTube Data API y autoriza tu cuenta.",
                    }
                )
            finally:
                self.jobs.publish_lock.release()

        threading.Thread(target=connect, daemon=True).start()
        return True

    def disconnect_youtube(self):
        if self.jobs.publish_lock.locked():
            return False
        youtube_share.disconnect()
        return True

    def share_portal(self, platform):
        import webbrowser

        if platform in social.PORTALS:
            webbrowser.open(social.PORTALS[platform])

    def publish_youtube(self, index, draft, privacy, kids):
        if not self.jobs.publish_lock.acquire(blocking=False):
            return False
        try:
            clip = self.jobs.status()["clips"][int(index)]
            if not clip.get("ready"):
                raise ValueError()
            receipt = Path(clip["path"]).with_suffix(".youtube.json")
            if receipt.exists():
                self.jobs.update(
                    social_status={
                        "busy": False,
                        "message": "Este clip ya se envió a YouTube. Revisa la publicación existente.",
                        "url": json.loads(receipt.read_text(encoding="utf-8"))["url"],
                    }
                )
                self.jobs.publish_lock.release()
                return False
            data = social.validate({"youtube": draft})["youtube"]
        except Exception:
            self.jobs.publish_lock.release()
            return False
        self.jobs.update(social_status={"busy": True, "message": "Subiendo a YouTube…"})

        def publish():
            try:
                path = clip.get("caption_path") or clip["path"]
                url = youtube_share.upload(
                    path if Path(path).is_file() else clip["path"],
                    data,
                    privacy,
                    kids,
                    lambda pct: self.jobs.update(
                        social_status={
                            "busy": True,
                            "message": f"Subiendo a YouTube: {pct}%",
                        }
                    ),
                )
                self.jobs.update(
                    social_status={
                        "busy": False,
                        "message": "Vídeo enviado a YouTube.",
                        "url": url,
                    }
                )
                Path(clip["path"]).with_suffix(".youtube.json").write_text(
                    json.dumps(
                        {
                            "url": url,
                            "privacy": privacy,
                            "uploaded_at": datetime.now().isoformat(),
                        }
                    ),
                    encoding="utf-8",
                )
            except Exception:
                self.jobs.update(
                    social_status={
                        "busy": False,
                        "message": "La subida no se confirmó. Revisa YouTube Studio antes de reintentar para evitar duplicados.",
                    }
                )
            finally:
                self.jobs.publish_lock.release()

        threading.Thread(target=publish, daemon=True).start()
        return True
