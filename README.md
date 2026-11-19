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

## Descargar e instalar

No hace falta instalar Python, Node ni herramientas extra.

1. Abre la [última release](https://github.com/EricCarballo/peakclip/releases/latest)
2. Descarga **`Peak-Clip-portable-windows.zip`**
3. Descomprime la carpeta donde quieras (por ejemplo el Escritorio)
4. Entra a `Peak Clip` y abre **`Peak Clip.exe`**

Importante: deja juntas las carpetas `_internal` y `tools` junto al `.exe`. No borres ni muevas solo el ejecutable.

La carpeta `tools` ya incluye `ffmpeg`, `yt-dlp` y `TwitchDownloaderCLI`.

## Cómo usarlo

1. Pega el enlace de un canal o VOD de **Twitch** o **Kick**
2. Elige una grabación **ya terminada** (en Kick, los que siguen en vivo no sirven)
3. Elige carpeta de destino y ajusta cantidad / sensibilidad si quieres
4. (Recomendado) Deja **Añadir subtítulos automáticamente** activo y elige plantilla
5. Pulsa generar clips; revisa el **mapa del chat** y confirma los momentos
6. Cuando termine, abre la carpeta de salida: MP4 verticales **1080×1920** y textos listos para redes

### Pestañas y temas

- Puedes abrir hasta **3 pestañas** para descargar/crear clips de distintos directos a la vez
- Cambia el tema (claro / oscuro / sistema) desde el encabezado
- Si hay una release nueva en GitHub, Peak Clip te avisa al abrir

### Subtítulos y textos

- Los títulos/descripciones se enriquecen con la **voz transcrita** del clip cuando hay subtítulos
- También puedes abrir **Añadir / Editar subtítulos** en cualquier clip del historial
- **Guardar como favorito** recuerda tu estilo de subtítulos
- **Renderizar muestra** muestra hasta 8 s con el acabado real
- El original se conserva; la exportación crea MP4 + SRT/ASS
- **Ver clip** / Explorador / publicar usan la versión subtitulada si existe

Consejos rápidos:

- En Kick, si un directo sigue en vivo, espera a que termine y vuelve a cargar el canal
- Si Kick limita peticiones (429), verás un aviso; la descarga se frena sola y reintenta
- Si Windows bloquea el `.exe` la primera vez, usa “Más información” → “Ejecutar de todos modos”
- Usa el acceso directo **Peak Clip** del Escritorio (apunta al portable más reciente tras cada build)

![Interfaz de Peak Clip](docs/screenshots/peak-clip-inicio.png)

---

## Para desarrolladores

La estructura y contratos de subtítulos están en [Arquitectura](docs/architecture.md).

```text
src/peakclip/   # aplicación Python
frontend/       # React + Vite
tests/          # pruebas
scripts/        # build portable
packaging/      # PyInstaller
```

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
