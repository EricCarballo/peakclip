"""Up to three independent clip sessions (tabs) sharing one media server."""

from __future__ import annotations
import itertools
import threading
from peakclip.application.clip_jobs import ClipJobs
from peakclip.application.social_controller import SocialController
from peakclip.application.history_controller import HistoryController
from peakclip.application.desktop_actions import DesktopActions
from peakclip.application.caption_controller import CaptionController
from peakclip.application.captions import CaptionService
from peakclip.infrastructure.caption_repository import JsonCaptionRepository
from peakclip.infrastructure.transcriber import FasterWhisperTranscriber
from peakclip.infrastructure.ass_renderer import FFmpegCaptionRenderer
from peakclip.infrastructure.media_server import MediaServer

MAX_TABS = 3


class TabSession:
    def __init__(self, tab_id, title, media, window_provider):
        self.id = tab_id
        self.title = title
        self.jobs = ClipJobs()
        self.social = SocialController(self.jobs, window_provider)
        self.history = HistoryController(self.jobs, window_provider)
        self.desktop = DesktopActions(self.jobs, window_provider)
        repository = JsonCaptionRepository()
        service = CaptionService(
            FasterWhisperTranscriber(self.jobs.run),
            repository,
            FFmpegCaptionRenderer(self.jobs.run),
        )
        self.captions = CaptionController(self.jobs, service, repository, media)
        self.jobs.caption_service = service

    def summary(self, active=False):
        state = self.jobs.status()
        label = self.title
        channel = state.get("channel")
        if channel:
            label = str(channel)
        elif state.get("video_title"):
            label = str(state.get("video_title"))[:28]
        return {
            "id": self.id,
            "title": label,
            "busy": bool(state.get("busy")),
            "stage": state.get("stage") or "idle",
            "message": state.get("message") or "",
            "active": active,
            "awaiting_peaks": bool(state.get("awaiting_peaks")),
            "rate_limited": bool(state.get("rate_limited")),
        }


class Workspace:
    def __init__(self, window_provider):
        self._window_provider = window_provider
        self._media = MediaServer()
        self._lock = threading.Lock()
        self._tabs = {}
        self._order = []
        self._active = None
        self._seq = itertools.count(1)
        self.new_tab()

    @property
    def media(self):
        return self._media

    def active(self) -> TabSession:
        with self._lock:
            return self._tabs[self._active]

    def tabs(self):
        with self._lock:
            return [
                self._tabs[tab_id].summary(active=(tab_id == self._active))
                for tab_id in self._order
            ]

    def new_tab(self):
        with self._lock:
            if len(self._order) >= MAX_TABS:
                return {
                    "ok": False,
                    "error": f"Máximo {MAX_TABS} pestañas a la vez para no saturar el equipo.",
                }
            tab_id = f"tab-{next(self._seq)}"
            title = f"Sesión {len(self._order) + 1}"
            session = TabSession(tab_id, title, self._media, self._window_provider)
            self._tabs[tab_id] = session
            self._order.append(tab_id)
            self._active = tab_id
            return {"ok": True, "id": tab_id, "tabs": self._summaries_unlocked()}

    def focus_tab(self, tab_id):
        with self._lock:
            if tab_id not in self._tabs:
                return {"ok": False, "error": "Esa pestaña ya no existe."}
            self._active = tab_id
            return {"ok": True, "id": tab_id, "tabs": self._summaries_unlocked()}

    def close_tab(self, tab_id):
        with self._lock:
            if tab_id not in self._tabs:
                return {"ok": False, "error": "Esa pestaña ya no existe."}
            if len(self._order) <= 1:
                return {
                    "ok": False,
                    "error": "Deja al menos una pestaña abierta.",
                }
            session = self._tabs[tab_id]
            if session.jobs.status().get("busy"):
                session.jobs.cancel()
            del self._tabs[tab_id]
            self._order = [item for item in self._order if item != tab_id]
            if self._active == tab_id:
                self._active = self._order[-1]
            return {"ok": True, "id": self._active, "tabs": self._summaries_unlocked()}

    def _summaries_unlocked(self):
        return [
            self._tabs[tab_id].summary(active=(tab_id == self._active))
            for tab_id in self._order
        ]

    def close(self):
        self._media.close()
