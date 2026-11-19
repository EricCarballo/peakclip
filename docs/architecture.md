# Arquitectura de Peak Clip

## Dependencias y responsabilidades

`api.py` es una fachada de métodos explícitos para pywebview y el punto de composición.
Sus colaboradores son privados para evitar que pywebview publique todo el grafo interno.

- `domain/`: análisis de picos, documentos de subtítulos, validación y plantillas versionadas. No importa pywebview, servicios HTTP ni FFmpeg.
- `application/`: coordinación de trabajos, pipeline de clips, historial, publicación y casos de uso de subtítulos.
- `application/ports.py`: contratos pequeños de transcripción, persistencia y renderizado. `CaptionService` recibe sus implementaciones; las pruebas pueden sustituirlas sin cargar un modelo o ejecutar FFmpeg.
- `infrastructure/`: herramientas, archivos, transcriptor local, renderizador ASS y reproducción local con soporte de rangos.
- `platforms/`: integración específica con Twitch y Kick.
- `frontend/src/components/`: presentación, editor de texto y selección de estilos. Las reglas de tiempos y la exportación se validan también en Python.

La extracción del pipeline conserva los contratos anteriores de pausa, historial y creación. La conversión vertical está centralizada en `FFmpegVideoProcessor`; el analizador de chat ya no ejecuta procesos ni incluye una segunda implementación de conversión.

## Subtítulos

1. Se crea y guarda el vídeo original.
2. Faster-whisper `base` multilingüe transcribe en CPU `int8` en un proceso independiente. La primera ejecución descarga el modelo en `%LOCALAPPDATA%/PeakClip/models`. Los siguientes trabajos reutilizan la descarga.
3. Las palabras mantienen tiempos relativos al clip. Se agrupan en frases cortas y se filtran silencios con VAD.
4. `clip.captions.json` guarda texto, tiempos y ajustes fuera de `.peakclip`. La limpieza de temporales no lo elimina.
5. El editor permite corregir frases y tiempos. Editar una frase redistribuye sus palabras dentro del intervalo: es una aproximación editable, no una nueva alineación acústica.
6. ASS define fuente, contorno, posición y efectos. FFmpeg incorpora esos subtítulos al MP4. También se exportan ASS y SRT; SRT contiene texto y tiempos, no animación.

Las plantillas son datos versionados del dominio y reutilizan efectos del renderizador. Añadir otro diseño con los efectos existentes no requiere modificar el pipeline. Un efecto nuevo requiere ampliar el adaptador y sus pruebas.

## Reproducción y archivos

La guía HTML del editor es aproximada. «Renderizar muestra» produce hasta ocho segundos con el mismo renderizador de la exportación final. Las fuentes Barlow se incluyen con sus licencias OFL, tanto en Vite como en PyInstaller.

El servidor de medios escucha solo en loopback, entrega únicamente archivos registrados mediante URLs aleatorias y soporta solicitudes Range. No expone directorios ni acepta rutas enviadas por HTTP.

Cada exportación usa un sufijo único. El original nunca se reemplaza. `caption_path` identifica la última versión exportada y se conserva en el historial. Reproducir, mostrar en carpeta y publicar usan esa versión si existe. Guardar cambios de texto por sí solo no modifica el MP4 ya exportado.

Una única operación de clips/subtítulos ocupa el estado de trabajo; mientras está activa no puede cambiarse de sesión. Cancelar termina el proceso hijo. Un fallo de transcripción automática conserva el vídeo y permite reintentar en el editor.

## Dependencias y pruebas

PyAV se limita a 16.x: la combinación probada de faster-whisper 1.2.1 con PyAV 19 falla por el parámetro `metadata_errors`. El modelo no se incluye en el paquete portable para no duplicarlo en cada actualización.

Pruebas: `python -m unittest discover -s tests -v`, con `PYTHONPATH=src`. Cubren tiempos, solapamientos, edición, escape de ASS, caché, conservación de archivos, historial y rangos HTTP, además de regresiones de Twitch/Kick. La comprobación manual de entrega incluye transcripción de voz sintética en español, renderizado de las cuatro plantillas, MP4/SRT/ASS y reproducción en el editor.

El refactor mantiene los adaptadores existentes de plataformas y publicación. La precisión de voz depende del ruido, el idioma y las voces superpuestas; el editor permite corregir los resultados.
