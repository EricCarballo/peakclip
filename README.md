# Peak Clip

<p align="center">
  <img src="assets/peak-clip.png" alt="Peak Clip" width="96" height="96">
</p>

<p align="center">
  <strong>Clips verticales listos para redes a partir de los picos del chat</strong><br>
  Twitch · Kick · Windows
</p>

<p align="center">
  <a href="https://github.com/EricCarballo/peakclip/releases/latest"><img src="https://img.shields.io/github/v/release/EricCarballo/peakclip?label=Descarga&color=0d9488" alt="Release"></a>
  <img src="https://img.shields.io/badge/Plataforma-Windows-0f172a" alt="Windows">
  <img src="https://img.shields.io/badge/Fuentes-Twitch%20%7C%20Kick-14b8a6" alt="Twitch Kick">
</p>

Peak Clip analiza el chat de un directo, encuentra los momentos con más reacción y genera clips verticales **1080×1920** con textos listos para copiar.

![Interfaz de Peak Clip](docs/screenshots/peak-clip-inicio.png)

## Estructura

```text
src/peakclip/          # aplicación Python (dominio, plataformas, infra, social)
frontend/              # interfaz React + Vite
tests/                 # pruebas unitarias
scripts/               # build / portable
packaging/             # PyInstaller
assets/                # iconos
docs/                  # capturas y docs
```

Capas (SOLID):
- **domain/** — análisis de chat y progreso
- **platforms/** — adaptadores Twitch / Kick
- **infrastructure/** — storage, rutas, herramientas
- **social/** — borradores y YouTube
- **api.py / app.py** — fachada pywebview y ventana

## Descarga (recomendado)

1. [Releases](https://github.com/EricCarballo/peakclip/releases/latest)
2. Descarga `Peak-Clip-portable-windows.zip`
3. Descomprime y abre `Peak Clip.exe`

La carpeta `tools` ya incluye `ffmpeg`, `yt-dlp` y `TwitchDownloaderCLI`.

## Desarrollo

```bash
npm --prefix frontend install
npm run build

python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
set PYTHONPATH=src
.venv\Scripts\python -m peakclip
```

Pruebas:

```bash
set PYTHONPATH=src
.venv\Scripts\python -m unittest discover -s tests -v
```

Empaquetar:

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\build_portable.ps1
```

## Licencia

Uso personal / compartir con amigos. Twitch, Kick y las herramientas de terceros conservan sus licencias.
