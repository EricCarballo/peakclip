"""Desktop bridge: explicit routes to composed application services."""

from __future__ import annotations
import json
from urllib.request import Request, urlopen

from peakclip.application.workspace import Workspace

window = None
APP_VERSION = "1.2.0"


class API:
    def __init__(self):
        self._workspace = Workspace(lambda: window)

    def _tab(self):
        return self._workspace.active()

    def status(self):
        state = self._tab().jobs.status()
        state["tabs"] = self._workspace.tabs()
        state["active_tab"] = self._tab().id
        state["app_version"] = APP_VERSION
        return state

    def tabs(self):
        return {"ok": True, "tabs": self._workspace.tabs(), "active": self._tab().id}

    def tab_new(self):
        return self._workspace.new_tab()

    def tab_focus(self, tab_id):
        return self._workspace.focus_tab(tab_id)

    def tab_close(self, tab_id):
        return self._workspace.close_tab(tab_id)

    def default_folder(self):
        return self._tab().jobs.default_folder()

    def inspect_link(self, value):
        return self._tab().jobs.inspect_link(value)

    def start(self, options):
        return self._tab().jobs.start(options)

    def resume(self):
        return self._tab().jobs.resume()

    def cancel(self):
        return self._tab().jobs.cancel()

    def confirm_peaks(self, ids):
        return self._tab().jobs.confirm_peaks(ids)

    def cleanup_temps(self):
        return self._tab().jobs.cleanup_temps()

    def social_draft(self, index):
        return self._tab().social.social_draft(index)

    def save_social(self, index, drafts):
        return self._tab().social.save_social(index, drafts)

    def social_accounts(self):
        return self._tab().social.social_accounts()

    def connect_youtube(self):
        return self._tab().social.connect_youtube()

    def disconnect_youtube(self):
        return self._tab().social.disconnect_youtube()

    def share_portal(self, platform):
        return self._tab().social.share_portal(platform)

    def publish_youtube(self, index, draft, privacy, kids):
        return self._tab().social.publish_youtube(index, draft, privacy, kids)

    def history_list(self):
        return self._tab().history.history_list()

    def history_open(self, path):
        return self._tab().history.history_open(path)

    def folder(self):
        return self._tab().desktop.folder()

    def open_folder(self):
        return self._tab().desktop.open_folder()

    def play(self, index):
        return self._tab().desktop.play(index)

    def twitch(self, index):
        return self._tab().desktop.twitch(index)

    def reveal(self, index):
        return self._tab().desktop.reveal(index)

    def open_url(self, url):
        return self._tab().desktop.open_url(url)

    def caption_catalog(self):
        return self._tab().captions.caption_catalog()

    def caption_open(self, index):
        return self._tab().captions.caption_open(index)

    def caption_transcribe(self, index, options=None):
        return self._tab().captions.caption_transcribe(index, options)

    def caption_save(self, index, document):
        return self._tab().captions.caption_save(index, document)

    def caption_export(self, index, document, preview=False):
        return self._tab().captions.caption_export(index, document, preview)

    def caption_media(self, index, rendered=False):
        return self._tab().captions.caption_media(index, rendered)

    def check_update(self):
        """Compare local portable version with the latest GitHub release tag."""
        try:
            req = Request(
                "https://api.github.com/repos/EricCarballo/peakclip/releases/latest",
                headers={
                    "User-Agent": "PeakClip",
                    "Accept": "application/vnd.github+json",
                },
            )
            with urlopen(req, timeout=8) as response:
                data = json.loads(response.read().decode())
            tag = str(data.get("tag_name") or "").lstrip("v")
            url = data.get("html_url") or "https://github.com/EricCarballo/peakclip/releases/latest"
            newer = bool(tag and tag != APP_VERSION)
            return {
                "ok": True,
                "current": APP_VERSION,
                "latest": tag or APP_VERSION,
                "newer": newer,
                "url": url,
            }
        except Exception:
            return {
                "ok": False,
                "current": APP_VERSION,
                "latest": APP_VERSION,
                "newer": False,
                "url": "https://github.com/EricCarballo/peakclip/releases/latest",
            }

    def close(self):
        self._workspace.close()
