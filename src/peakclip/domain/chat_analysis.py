"""Pure chat peak analysis: no network, CLI or video encoding dependencies."""
import json
import re
import statistics

# Mensajes que cuentan doble: risas y reacciones típicas del chat en español e inglés.
REACCIONES = re.compile(
    r"(ja){2,}|j{2,}a|xd+|kekw|lul|omegalul|lmao+|clip|noo+|wtf|pog|😂|🤣|💀",
    re.IGNORECASE,
)


def leer_chat(ruta):
    with open(ruta, encoding="utf-8") as f:
        datos = json.load(f)
    mensajes = []
    for c in datos.get("comments", []):
        t = c.get("content_offset_seconds")
        texto = (c.get("message") or {}).get("body", "")
        if t is not None:
            mensajes.append((float(t), texto))
    vod = (datos.get("video") or {}).get("id")
    return mensajes, vod


def contar(mensajes, ventana):
    """Puntos de cada tramo de `ventana` segundos: 1 por mensaje, 2 si es una reacción."""
    if not mensajes:
        return []
    fin = max(t for t, _ in mensajes)
    tramos = [0.0] * (int(fin // ventana) + 1)
    for t, texto in mensajes:
        tramos[int(t // ventana)] += 2 if REACCIONES.search(texto) else 1
    return tramos


def buscar_picos(tramos, ventana, cuantos, separacion, minimo):
    """Un pico es un tramo muy por encima de lo normal en los 5 minutos de alrededor."""
    radio = max(1, int(300 // ventana))
    candidatos = []
    for i, v in enumerate(tramos):
        vecinos = tramos[max(0, i - radio): i] + tramos[i + 1: i + 1 + radio]
        normal = statistics.median(vecinos) if vecinos else 0
        fuerza = v / max(normal, 1.0)
        if fuerza >= minimo:
            candidatos.append((fuerza, i, v, normal))
    candidatos.sort(reverse=True)
    elegidos = []
    for fuerza, i, v, normal in candidatos:
        if all(abs(i - j) * ventana >= separacion for _, j, _, _ in elegidos):
            elegidos.append((fuerza, i, v, normal))
        if len(elegidos) == cuantos:
            break
    return sorted(elegidos, key=lambda e: e[1])


def hms(s):
    s = int(max(0, s))
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"
