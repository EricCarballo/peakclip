"""Isolated inference process: cancellation can terminate it and release all RAM."""

import json
import sys
from pathlib import Path


def main(args=None):
    source, output, cache, duration = args or sys.argv[1:]
    from faster_whisper import WhisperModel
    from peakclip.domain.captions import group_words

    model = WhisperModel(
        "base", device="cpu", compute_type="int8", download_root=cache, cpu_threads=4
    )
    segments, info = model.transcribe(
        source, word_timestamps=True, vad_filter=True, beam_size=5
    )
    words = []
    for segment in segments:
        words.extend(
            dict(start=w.start, end=w.end, text=w.word) for w in (segment.words or [])
        )
        print(
            "CAPTION_PROGRESS=" + str(min(99, segment.end / float(duration) * 100)),
            flush=True,
        )
    result = dict(
        version=1, language=info.language, cues=group_words(words, float(duration))
    )
    Path(output).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
