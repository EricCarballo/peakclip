"""clips_chat.py: encuentra los mejores momentos de un directo de Twitch mirando el chat
y los corta en vídeo vertical para Reels, TikTok y Shorts.

La idea: cuando pasa algo en directo, el chat explota. Ese pico es tu clip.
El chat reacciona tarde, así que el clip empieza 20 segundos antes del pico.

Necesitas:
  - Python 3.9 o más nuevo (sin instalar nada más para la parte del chat).
  - El chat del directo en JSON, bajado con TwitchDownloader (gratis, código abierto):
      TwitchDownloaderCLI chatdownload --id <id del vídeo> -o chat.json
  - Para cortar el vídeo: yt-dlp y ffmpeg instalados.

Uso:
  python3 clips_chat.py chat.json                     # solo lista los picos
  python3 clips_chat.py chat.json --vod <id> --cortar # además baja y corta los clips

Úsalo solo con creadores que permiten que se recorten sus directos.
"""
import argparse
import json
import os
import re
import shutil
import statistics
import subprocess
import sys

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


def cortar(vod, inicio, fin, salida):
    """Baja solo ese trozo del directo y lo pasa a vertical 1080x1920 con fondo difuminado."""
    for prog in ("yt-dlp", "ffmpeg"):
        if not shutil.which(prog):
            sys.exit(f"Falta {prog}: instálalo para poder cortar los clips.")
    bruto = salida + ".bruto.mp4"
    subprocess.run(
        ["yt-dlp", "-q", "--no-warnings", "-f", "best[height<=1080]",
         "--download-sections", f"*{inicio:.0f}-{fin:.0f}", "--force-keyframes-at-cuts",
         "-o", bruto, f"https://www.twitch.tv/videos/{vod}"],
        check=True,
    )
    filtro = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:2[fondo];"
        "[0:v]scale=1080:-2[delante];[fondo][delante]overlay=(W-w)/2:(H-h)/2"
    )
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", bruto, "-filter_complex", filtro,
         "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-c:a", "aac", salida],
        check=True,
    )
    os.remove(bruto)


def main():
    p = argparse.ArgumentParser(description="Clips de un directo a partir de los picos del chat.")
    p.add_argument("chat", help="chat.json de TwitchDownloader")
    p.add_argument("--vod", help="id del vídeo de Twitch (si no, se lee del chat)")
    p.add_argument("--cortar", action="store_true", help="bajar y cortar los clips en vertical")
    p.add_argument("--clips", type=int, default=10, help="cuántos clips (10)")
    p.add_argument("--ventana", type=int, default=10, help="segundos por tramo (10)")
    p.add_argument("--antes", type=int, default=20, help="segundos antes del pico (20)")
    p.add_argument("--despues", type=int, default=15, help="segundos después del pico (15)")
    p.add_argument("--minimo", type=float, default=3.0, help="veces por encima de lo normal (3)")
    p.add_argument("--carpeta", default="clips", help="carpeta de salida (clips)")
    a = p.parse_args()

    mensajes, vod_chat = leer_chat(a.chat)
    if not mensajes:
        sys.exit("El chat está vacío o no es un JSON de TwitchDownloader.")
    vod = a.vod or vod_chat
    tramos = contar(mensajes, a.ventana)
    picos = buscar_picos(tramos, a.ventana, a.clips, separacion=90, minimo=a.minimo)
    print(f"{len(mensajes)} mensajes · {len(picos)} picos\n")
    if not picos:
        sys.exit("No hay picos claros. Prueba con --minimo 2.")

    if a.cortar:
        if not vod:
            sys.exit("Falta --vod con el id del vídeo.")
        os.makedirs(a.carpeta, exist_ok=True)
    for n, (fuerza, i, v, normal) in enumerate(picos, 1):
        pico = i * a.ventana
        inicio, fin = max(0, pico - a.antes), pico + a.ventana + a.despues
        enlace = f"https://www.twitch.tv/videos/{vod}?t={pico // 3600}h{pico % 3600 // 60}m{pico % 60}s" if vod else ""
        print(f"{n:2d}. {hms(inicio)} → {hms(fin)}  ×{fuerza:.1f} ({v:.0f} frente a {normal:.0f})  {enlace}")
        if a.cortar:
            salida = os.path.join(a.carpeta, f"clip{n:02d}_{hms(pico).replace(':', '-')}.mp4")
            cortar(vod, inicio, fin, salida)
            print(f"    → {salida}")


if __name__ == "__main__":
    main()
