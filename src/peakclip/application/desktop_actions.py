import os, subprocess
from pathlib import Path
import webview
from peakclip.infrastructure.storage import DEFAULT_OUTPUT


def clip_media_path(clip):
    """Prefer the latest subtitled export; fall back to the original MP4."""
    if not clip or not clip.get("ready"):
        return None
    for key in ("caption_path", "path"):
        value = clip.get(key)
        if value and Path(value).is_file():
            return str(Path(value))
    return None


class DesktopActions:
    def __init__(self, jobs, window_provider):
        self.jobs = jobs
        self.window_provider = window_provider

    def folder(self):
        result = self.window_provider().create_file_dialog(webview.FileDialog.FOLDER)
        return result[0] if result else ""

    def open_folder(self):
        try:
            target = getattr(self.jobs, "output", DEFAULT_OUTPUT)
            target.mkdir(parents=True, exist_ok=True)
            os.startfile(str(target))
        except OSError:
            self.jobs.update(
                message="No se puede abrir la carpeta. Elige una carpeta local disponible.",
                output_error=True,
            )

    def play(self, index):
        clip = self.jobs.status()["clips"][int(index)]
        path = clip_media_path(clip)
        if not path:
            self.jobs.update(
                message="No encontramos el vídeo de ese clip. ¿Se movió o borró la carpeta?"
            )
            return
        try:
            # Opens with the Windows default player (Fotos / Films & TV / etc.).
            os.startfile(path)
        except OSError:
            self.jobs.update(
                message="Windows no pudo abrir el vídeo. Prueba «Abrir carpeta» y ábrelo desde el Explorador."
            )

    def twitch(self, index):
        import webbrowser

        webbrowser.open(self.jobs.status()["clips"][int(index)]["url"])

    def reveal(self, index):
        clip = self.jobs.status()["clips"][int(index)]
        path = clip_media_path(clip)
        if not path:
            self.jobs.update(
                message="No encontramos el archivo de ese clip en su carpeta."
            )
            return
        try:
            subprocess.Popen(["explorer.exe", "/select,", path])
        except OSError:
            self.jobs.update(message="No se pudo mostrar el archivo en el Explorador.")
