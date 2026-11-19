"""Video encoding adapter. Clip geometry lives outside the use-case pipeline."""

VERTICAL_FILTER = "[0:v]split=2[b][f];[b]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:2[bg];[f]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2"


def media_duration(source):
    import av

    with av.open(str(source)) as container:
        if container.duration:
            return float(container.duration / av.time_base)
    raise ValueError("No se pudo leer la duración del clip.")


class FFmpegVideoProcessor:
    def __init__(self, runner):
        self.runner = runner

    def vertical(self, source, destination, duration):
        self.runner(
            [
                "ffmpeg",
                "-n",
                "-nostats",
                "-progress",
                "pipe:1",
                "-i",
                str(source),
                "-filter_complex",
                VERTICAL_FILTER,
                "-c:v",
                "libx264",
                "-crf",
                "20",
                "-preset",
                "veryfast",
                "-c:a",
                "aac",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(destination),
            ],
            stage="encode",
            duration=duration,
        )

    def thumbnail(self, source, destination):
        self.runner(
            [
                "ffmpeg",
                "-v",
                "error",
                "-n",
                "-ss",
                "1",
                "-i",
                str(source),
                "-frames:v",
                "1",
                "-vf",
                "scale=480:270:force_original_aspect_ratio=decrease,pad=480:270:(ow-iw)/2:(oh-ih)/2",
                "-q:v",
                "4",
                str(destination),
            ]
        )
