from pathlib import Path
from peakclip.infrastructure.storage import (
    DEFAULT_OUTPUT,
    list_history,
    load_history,
    temps_present,
)


class HistoryController:
    def __init__(self, jobs, window_provider):
        self.jobs = jobs
        self.window_provider = window_provider

    def history_list(self):
        try:
            roots = [DEFAULT_OUTPUT]
            folder = getattr(self.jobs, "output", None)
            if folder:
                try:
                    parents = Path(folder).parents
                    roots.append(
                        parents[1] if len(parents) > 1 else Path(folder).parent
                    )
                except Exception:
                    pass
            return {"ok": True, "items": list_history(roots)}
        except Exception:
            return {"ok": False, "error": "No se pudo leer el historial.", "items": []}

    def history_open(self, path):
        if self.jobs.state.get("busy"):
            return {"ok": False, "error": "Espera a que termine el proceso actual."}
        try:
            data = load_history(path)
        except FileNotFoundError as e:
            return {"ok": False, "error": str(e)}
        except Exception:
            return {"ok": False, "error": "No se pudo abrir esa sesión del historial."}
        if not data.get("clips"):
            return {"ok": False, "error": "Esa carpeta ya no tiene clips."}
        folder = Path(data["path"])
        self.jobs.output = folder
        self.jobs.update(
            clips=data["clips"],
            output_folder=str(folder),
            channel=data.get("channel") or "",
            video_title=data.get("title") or "",
            folder_label=data.get("folder_label") or folder.name,
            platform=data.get("platform") or "twitch",
            from_history=True,
            stage="done",
            message=f"Historial · {data.get('channel') or 'canal'} · {len(data['clips'])} clips. Puedes copiar los textos otra vez.",
            output_error=False,
            temps_available=temps_present(folder),
            logs=[],
            events=[],
            current=0,
            total=len(data["clips"]),
            completed=len(data["clips"]),
            stage_progress=None,
            speed="",
            eta="",
        )
        return {
            "ok": True,
            "clips": len(data["clips"]),
            "channel": data.get("channel") or "",
            "title": data.get("title") or "",
        }
