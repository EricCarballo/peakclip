"""ASS typography and FFmpeg rendering share one source of truth."""

import tempfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from peakclip.domain.captions import TEMPLATES
from peakclip.infrastructure.paths import bundle_root


def stamp(seconds, srt=False):
    ticks = max(0, round(seconds * (1000 if srt else 100)))
    scale = 1000 if srt else 100
    whole, fraction = divmod(ticks, scale)
    h, rem = divmod(whole, 3600)
    m, s = divmod(rem, 60)
    return (
        f"{h:02}:{m:02}:{s:02},{fraction:03}"
        if srt
        else f"{h}:{m:02}:{s:02}.{fraction:02}"
    )


def escape(text):
    # Untrusted transcription must never become an ASS override or a line break tag.
    return (
        text.replace("\\", "＼")
        .replace("{", "｛")
        .replace("}", "｝")
        .replace("\n", " ")
    )


def ass_color(value):
    return "&H00" + value[5:7] + value[3:5] + value[1:3]


def wrap_words(words, size, condensed=False):
    # Conservative width budget for a 1080px portrait frame, maximum two lines.
    limit = max(12, int(900 / (size * (0.43 if condensed else 0.54))))
    total = sum(len(w) for w in words) + len(words) - 1
    if total <= limit or len(words) < 2:
        return None
    best = min(
        range(1, len(words)),
        key=lambda i: abs(len(" ".join(words[:i])) - len(" ".join(words[i:]))),
    )
    return best


def to_ass(document):
    config = document["settings"]
    template = next(t for t in TEMPLATES if t.id == config["template"])
    y = {"upper": 420, "middle": 960, "lower": 1400}[config["position"]]
    band = template.effect == "band"
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{template.font},{config["size"]},&H00FFFFFF,&H00FFFFFF,&H00111111,&H70000000,0,0,0,0,100,100,0,0,{3 if band else 1},{14 if band else 4},{0 if band else 2},5,90,90,250,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    rows = []
    for cue in document["cues"]:
        words = cue["words"]
        # Fit corrected long phrases rather than clipping beyond the video edges.
        longest_line = max(len(cue["text"]) / 2, max(len(w["text"]) for w in words))
        size = min(
            config["size"],
            max(
                20,
                int(
                    880 / (longest_line * (0.43 if template.effect == "pop" else 0.54))
                ),
            ),
        )
        split = wrap_words([w["text"] for w in words], size, template.effect == "pop")
        base = f"{{\\an5\\pos(540,{y})\\fs{size}}}"
        motion = ""
        if config["motion"]:
            if template.effect == "pop":
                motion = "{\\fscx92\\fscy92\\t(0,130,\\fscx100\\fscy100)\\fad(50,90)}"
            elif template.effect in ("fade", "band"):
                motion = "{\\fad(100,120)}"

        def line(active=-1):
            pieces = []
            for i, word in enumerate(words):
                if i:
                    pieces.append("\\N" if i == split else " ")
                color = ass_color(config["color"]) if i == active else "&H00FFFFFF"
                pieces.append("{\\1c" + color + "}" + escape(word["text"]))
            return "".join(pieces)

        def event(start, end, text):
            if end - start >= 0.01:
                rows.append(
                    f"Dialogue: 0,{stamp(start)},{stamp(end)},Default,,0,0,0,,{base}{motion}{text}"
                )

        if template.effect == "highlight" and config["motion"]:
            cursor = cue["start"]
            for i, word in enumerate(words):
                event(cursor, word["start"], line())
                event(word["start"], word["end"], line(i))
                cursor = word["end"]
            event(cursor, cue["end"], line())
        else:
            event(cue["start"], cue["end"], line())
    return header + "\n".join(rows) + "\n"


def to_srt(document):
    return (
        "\n\n".join(
            f"{i}\n{stamp(c['start'], True)} --> {stamp(c['end'], True)}\n{c['text']}"
            for i, c in enumerate(document["cues"], 1)
        )
        + "\n"
    )


class FFmpegCaptionRenderer:
    def __init__(self, runner):
        self.runner = runner

    def render(self, source: Path, document, duration, preview=False):
        folder = (
            source.parent / ".peakclip" / "caption-previews"
            if preview
            else source.parent
        )
        folder.mkdir(parents=True, exist_ok=True)
        suffix = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_" + uuid4().hex[:8]
        dest = folder / (source.stem + "_subtitulos_" + suffix + ".mp4")
        # Relative safe ASS filename avoids FFmpeg filter escaping bugs on Windows.
        with tempfile.TemporaryDirectory(prefix="peakclip-captions-") as temp:
            root = Path(temp)
            (root / "captions.ass").write_text(to_ass(document), encoding="utf-8-sig")
            import shutil

            shutil.copytree(bundle_root() / "assets" / "fonts", root / "fonts")
            args = [
                "ffmpeg",
                "-n",
                "-nostats",
                "-progress",
                "pipe:1",
                "-i",
                str(source.resolve()),
            ]
            if preview:
                args += ["-t", str(min(duration, 8))]
            args += [
                "-vf",
                "ass=captions.ass:fontsdir=fonts"
                + (",scale=360:640" if preview else ""),
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23" if preview else "20",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
                "-pix_fmt",
                "yuv420p",
                str(dest.resolve()),
            ]
            try:
                self.runner(
                    args,
                    stage="encode",
                    duration=min(duration, 8) if preview else duration,
                    cwd=temp,
                )
            except Exception:
                dest.unlink(missing_ok=True)
                raise
        if not preview:
            dest.with_suffix(".ass").write_text(to_ass(document), encoding="utf-8-sig")
            dest.with_suffix(".srt").write_text(to_srt(document), encoding="utf-8")
        return dest
