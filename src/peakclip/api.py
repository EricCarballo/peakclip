"""Desktop bridge: explicit routes to composed application services."""

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

window = None


class API:
    def __init__(self):
        self._jobs = ClipJobs()
        self._media = MediaServer()
        provider = lambda: window
        self._social = SocialController(self._jobs, provider)
        self._history = HistoryController(self._jobs, provider)
        self._desktop = DesktopActions(self._jobs, provider)
        repository = JsonCaptionRepository()
        service = CaptionService(
            FasterWhisperTranscriber(self._jobs.run),
            repository,
            FFmpegCaptionRenderer(self._jobs.run),
        )
        self._captions = CaptionController(self._jobs, service, repository, self._media)
        self._jobs.caption_service = service

    def default_folder(self):
        return self._jobs.default_folder()

    def status(self):
        return self._jobs.status()

    def inspect_link(self, value):
        return self._jobs.inspect_link(value)

    def start(self, options):
        return self._jobs.start(options)

    def resume(self):
        return self._jobs.resume()

    def cancel(self):
        return self._jobs.cancel()

    def cleanup_temps(self):
        return self._jobs.cleanup_temps()

    def social_draft(self, index):
        return self._social.social_draft(index)

    def save_social(self, index, drafts):
        return self._social.save_social(index, drafts)

    def social_accounts(self):
        return self._social.social_accounts()

    def connect_youtube(self):
        return self._social.connect_youtube()

    def disconnect_youtube(self):
        return self._social.disconnect_youtube()

    def share_portal(self, platform):
        return self._social.share_portal(platform)

    def publish_youtube(self, index, draft, privacy, kids):
        return self._social.publish_youtube(index, draft, privacy, kids)

    def history_list(self):
        return self._history.history_list()

    def history_open(self, path):
        return self._history.history_open(path)

    def folder(self):
        return self._desktop.folder()

    def open_folder(self):
        return self._desktop.open_folder()

    def play(self, index):
        return self._desktop.play(index)

    def twitch(self, index):
        return self._desktop.twitch(index)

    def reveal(self, index):
        return self._desktop.reveal(index)

    def caption_catalog(self):
        return self._captions.caption_catalog()

    def caption_open(self, index):
        return self._captions.caption_open(index)

    def caption_transcribe(self, index, options=None):
        return self._captions.caption_transcribe(index, options)

    def caption_save(self, index, document):
        return self._captions.caption_save(index, document)

    def caption_export(self, index, document, preview=False):
        return self._captions.caption_export(index, document, preview)

    def caption_media(self, index, rendered=False):
        return self._captions.caption_media(index, rendered)
