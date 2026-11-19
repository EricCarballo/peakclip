"""Caption documents and validation. Times are relative to the clip, in seconds."""

from dataclasses import dataclass, asdict
import math
import re


@dataclass(frozen=True)
class CaptionTemplate:
    id: str
    name: str
    description: str
    font: str
    effect: str
    size: int


TEMPLATES = (
    CaptionTemplate(
        "focus",
        "En foco",
        "La palabra que escuchas toma el color.",
        "Barlow SemiBold",
        "highlight",
        76,
    ),
    CaptionTemplate(
        "impact",
        "Impacto",
        "Frases cortas con una entrada enérgica.",
        "Barlow Condensed",
        "pop",
        92,
    ),
    CaptionTemplate(
        "editorial",
        "Editorial",
        "Dos líneas limpias, con una transición suave.",
        "Barlow SemiBold",
        "fade",
        68,
    ),
    CaptionTemplate(
        "contrast",
        "Contraste",
        "Una banda oscura mantiene el texto legible.",
        "Barlow SemiBold",
        "band",
        68,
    ),
)


def catalog():
    return [asdict(template) for template in TEMPLATES]


def settings(value=None):
    value = value or {}
    template_id = value.get("template", "focus")
    template = next((t for t in TEMPLATES if t.id == template_id), None)
    if template is None:
        raise ValueError("Elige una plantilla de subtítulos válida.")
    size = int(value.get("size", template.size))
    position = value.get("position", "lower")
    color = value.get("color", "#F8D34F")
    motion = value.get("motion", True)
    if not 44 <= size <= 110 or position not in ("upper", "middle", "lower"):
        raise ValueError("Revisa el tamaño y la posición de los subtítulos.")
    if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        raise ValueError("Elige un color válido.")
    if not isinstance(motion, bool):
        raise ValueError("La animación debe estar activada o desactivada.")
    return dict(
        template=template_id, size=size, position=position, color=color, motion=motion
    )


def validate_document(document, duration):
    if not isinstance(document, dict) or not isinstance(document.get("cues"), list):
        raise ValueError("No se pudo leer el documento de subtítulos.")
    result = {
        "version": 1,
        "language": str(document.get("language", "es"))[:12],
        "settings": settings(document.get("settings")),
        "cues": [],
    }
    if len(document["cues"]) > 2000:
        raise ValueError("Hay demasiadas frases en este clip.")
    previous_end = 0
    for row in document["cues"]:
        start, end = float(row["start"]), float(row["end"])
        text = " ".join(str(row.get("text", "")).split())
        if not text or len(text) > 160:
            raise ValueError("Cada frase debe tener entre 1 y 160 caracteres.")
        if any(len(word) > 40 for word in text.split()):
            raise ValueError(
                "Divide las palabras de más de 40 caracteres para que quepan en pantalla."
            )
        if (
            not all(math.isfinite(n) for n in (start, end))
            or start < previous_end - 0.001
            or end <= start
            or end > duration + 0.05
        ):
            raise ValueError(
                "Las frases deben estar ordenadas, sin superponerse y dentro del clip."
            )
        words = []
        for word in row.get("words", []):
            a, b = float(word["start"]), float(word["end"])
            if (
                not all(math.isfinite(n) for n in (a, b))
                or a < start
                or b > end + 0.001
                or b <= a
                or (words and a < words[-1]["end"] - 0.001)
            ):
                raise ValueError("Los tiempos de las palabras no son válidos.")
            words.append({"start": a, "end": b, "text": str(word["text"]).strip()})
        # Text/timing edits invalidate old word alignment. Redistribute within this phrase.
        if not words or " ".join(w["text"] for w in words) != text:
            parts = text.split()
            step = (end - start) / len(parts)
            words = [
                dict(start=start + i * step, end=start + (i + 1) * step, text=w)
                for i, w in enumerate(parts)
            ]
        result["cues"].append(dict(start=start, end=end, text=text, words=words))
        previous_end = end
    return result


def group_words(words, duration):
    """Short readable phrases; preserve actual timestamps including silence."""
    groups, current = [], []
    for raw in words:
        text = str(raw.get("text", "")).strip()
        start, end = max(0.0, float(raw["start"])), min(duration, float(raw["end"]))
        if not text or end <= start:
            continue
        if current and (
            len(current) >= 5
            or len(" ".join(w["text"] for w in current)) + len(text) > 34
            or start - current[-1]["end"] > 0.6
        ):
            groups.append(current)
            current = []
        floor = (
            current[-1]["end"] if current else (groups[-1][-1]["end"] if groups else 0)
        )
        start = max(start, floor)
        if end <= start:
            continue
        current.append(dict(start=start, end=end, text=text))
        if text.endswith((".", "!", "?", "…")):
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return [
        dict(
            start=g[0]["start"],
            end=g[-1]["end"],
            text=" ".join(w["text"] for w in g),
            words=g,
        )
        for g in groups
    ]
