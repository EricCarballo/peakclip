import json
from pathlib import Path
from uuid import uuid4


class JsonCaptionRepository:
    def load(self, source: Path):
        target = source.with_suffix(".captions.json")
        if not target.exists():
            return None
        return json.loads(target.read_text(encoding="utf-8"))

    def save(self, source: Path, document):
        target = source.with_suffix(".captions.json")
        temp = target.with_name(target.name + "." + uuid4().hex + ".tmp")
        try:
            temp.write_text(
                json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            temp.replace(target)
        finally:
            temp.unlink(missing_ok=True)
