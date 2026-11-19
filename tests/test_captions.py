import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from peakclip.domain.captions import settings, group_words, validate_document, catalog
from peakclip.application.captions import CaptionService
from peakclip.infrastructure.caption_repository import JsonCaptionRepository
from peakclip.infrastructure.ass_renderer import to_ass, to_srt
from peakclip.infrastructure.media_server import MediaServer
from peakclip.infrastructure.storage import (
    cleanup_workspace,
    save_session,
    load_history,
)


def document():
    words = [
        dict(start=0.1, end=0.6, text="Hola"),
        dict(start=0.8, end=1.4, text="mundo"),
    ]
    return dict(settings=settings(), cues=group_words(words, 2), language="es")


class Captions(unittest.TestCase):
    def test_word_times_and_silence_survive_grouping(self):
        doc = validate_document(document(), 2)
        self.assertEqual(doc["cues"][0]["words"][1]["start"], 0.8)
        self.assertIn("0:00:00.60,0:00:00.80", to_ass(doc))

    def test_edit_redistributes_words_within_phrase(self):
        doc = document()
        doc["cues"][0]["text"] = "Hola a todo el mundo"
        result = validate_document(doc, 2)["cues"][0]
        self.assertEqual(len(result["words"]), 5)
        self.assertAlmostEqual(result["words"][-1]["end"], 1.4)

    def test_invalid_times_and_overlaps_rejected(self):
        for start, end in [
            (float("nan"), 1),
            (0, float("inf")),
            (-1, 1),
            (1, 0.5),
            (0, 5),
        ]:
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                validate_document(
                    dict(cues=[dict(start=start, end=end, text="hola")]), 2
                )
        doc = document()
        doc["cues"] *= 2
        with self.assertRaises(ValueError):
            validate_document(doc, 2)

    def test_escape_ass_injection(self):
        doc = document()
        doc["cues"][0]["text"] = r"{\pos(0,0)} hola"
        doc = validate_document(doc, 2)
        rendered = to_ass(doc)
        self.assertNotIn(r"{\pos(0,0)}", rendered)
        self.assertIn("｛", rendered)

    def test_each_template_renders_and_motion_can_be_disabled(self):
        for template in catalog():
            doc = document()
            doc["settings"] = settings(dict(template=template["id"], motion=False))
            ass = to_ass(validate_document(doc, 2))
            self.assertIn("Dialogue:", ass)
            self.assertNotIn("\\t(", ass)
            self.assertNotIn("\\fad(", ass)

    def test_srt_timestamps(self):
        self.assertIn("00:00:00,100 --> 00:00:01,400", to_srt(document()))

    def test_cached_transcript_survives_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "clip1.mp4"
            source.write_bytes(b"original")
            repo = JsonCaptionRepository()
            asr = Mock()
            asr.transcribe.return_value = document()
            service = CaptionService(asr, repo, Mock())
            service.prepare(source, 2, settings(), Mock())
            edited = repo.load(source)
            edited["cues"][0]["text"] = "Corrección guardada"
            service.save(source, 2, edited)
            scratch = Path(tmp) / ".peakclip"
            scratch.mkdir()
            (scratch / "cache").write_bytes(b"temp")
            cleanup_workspace(tmp)
            loaded = service.prepare(
                source, 2, settings(dict(template="impact")), Mock()
            )
            self.assertEqual(loaded["cues"][0]["text"], "Corrección guardada")
            asr.transcribe.assert_called_once()
            self.assertEqual(source.read_bytes(), b"original")

    def test_empty_transcript_cannot_export(self):
        service = CaptionService(Mock(), Mock(), Mock())
        with self.assertRaisesRegex(ValueError, "No hay voz"):
            service.export("clip.mp4", 2, dict(cues=[]))

    def test_history_preserves_subtitle_version(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("peakclip.infrastructure.storage.remember_history"),
        ):
            source = Path(tmp) / "clip1.mp4"
            source.write_bytes(b"video")
            rendered = Path(tmp) / "clip1_subtitulos_test.mp4"
            rendered.write_bytes(b"captioned")
            save_session(
                tmp,
                [
                    dict(
                        number=1,
                        ready=True,
                        path=str(source),
                        duration=2,
                        caption_path=str(rendered),
                    )
                ],
            )
            self.assertEqual(
                load_history(tmp)["clips"][0]["caption_path"], str(rendered)
            )

    def test_media_server_ranges_and_unregistered_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "clip.mp4"
            source.write_bytes(b"0123456789")
            server = MediaServer()
            try:
                url = server.url(source)
                with urlopen(Request(url, headers={"Range": "bytes=3-5"})) as response:
                    self.assertEqual(response.status, 206)
                    self.assertEqual(response.read(), b"345")
                with self.assertRaises(HTTPError):
                    urlopen(url.replace(url.rsplit("/", 1)[1], "arbitrary.mp4"))
            finally:
                server.close()

    def test_busy_job_rejects_transcription(self):
        from peakclip.api import API

        api = API()
        api._jobs.update(busy=True)
        self.assertFalse(api.caption_transcribe(0)["ok"])

    def test_native_viewer_prefers_subtitled_file(self):
        from peakclip.application.desktop_actions import clip_media_path

        with tempfile.TemporaryDirectory() as tmp:
            original = Path(tmp) / "clip.mp4"
            captioned = Path(tmp) / "clip_subtitulos.mp4"
            original.write_bytes(b"orig")
            captioned.write_bytes(b"cap")
            clip = {
                "ready": True,
                "path": str(original),
                "caption_path": str(captioned),
            }
            self.assertEqual(clip_media_path(clip), str(captioned))
            captioned.unlink()
            self.assertEqual(clip_media_path(clip), str(original))
            original.unlink()
            self.assertIsNone(clip_media_path(clip))


if __name__ == "__main__":
    unittest.main()
