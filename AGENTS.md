# AGENTS.md — VoxDub (traductor/doblador de video local)

## Propósito
App de escritorio que traduce y dobla videos **locales** a otro idioma, con voz TTS
estándar asignada por género del hablante y override manual desde un archivo de voces IA.
Pipeline: transcribir → detectar hablantes/género → traducir → sintetizar → lip-sync → mux.

## Regla de ingeniería (OBLIGATORIA)
**Hacer → auditar → recién avanzar.** Cada etapa del pipeline tiene un smoke test
que debe quedar VERDE antes de marcar la fase como `done`. En CI se corre el pipeline
"dorado" en cada cambio; si falla, no se mergea.

## Alcance legal (estricto)
- Solo se procesa contenido **propio o autorizado** (el usuario aporta el archivo).
- Cero red por defecto: modelos locales. Si se usa API externa, requiere consentimiento.
- No se clona la voz de personas reales; solo TTS estándar/generado por IA.

## Arquitectura
- Backend Python (FastAPI) con etapas desacopladas vía interfaces (`pipeline/interfaces.py`).
- Cada etapa devuelve `StageResult` con `status` y `metrics`; el orquestador audita.
- Frontend React + Tailwind empaquetado con Tauri (ver `docs/ARCHITECTURE.md`).
- Fase 1 implementada: `transcribe` (Whisper opcional + Mock verificable offline).

## Comandos
- Fase 1: `PYTHONPATH=src/backend python -m voxdub.cli transcribe <video> [--mock]`
- Fase 1..4: `PYTHONPATH=src/backend python -m voxdub.cli synthesize <video> [--mock]`
- App en un comando: `PYTHONPATH=src/backend python -m voxdub.cli serve` (API + frontend compilado)
- Binario autónomo: `python scripts/build_backend.py` → `dist_backend/voxdub-backend` (onefile, 42 MB)
- Sidecar Tauri: `bash scripts/prepare_tauri_sidecar.sh <target-triple>` (build + copia a `web/src-tauri/binaries/`)
- Smoke tests: `PYTHONPATH=src/backend python -m unittest discover -s tests`
- Voces reales: `python scripts/fetch_voice.py --name <base> --url <URL> --sha256 <hash>`

## Seguridad / supply-chain
- `piper-tts` ya instalado y verificado en este entorno. El resto va por `requirements.txt` (pinnear versiones).
- Los pesos de voz se descargan SOLO vía `scripts/fetch_voice.py` con SHA256 verificado; no se confía ciegamente en URLs.
- Cero red por defecto en el pipeline; modelos locales. Si se usa API externa, requiere consentimiento explícito.

## Auditoría final (PENDIENTE — ejecutar cuando la app esté terminada)
Cuando VoxDub esté completa, hacer una pasada de **revisión de problemas de usuario (UX/edge-cases)**:
recorrer la app buscando puntos donde el usuario pueda frustrarse o encontrar errores al interactuar
(estados de error no informados, archivos inválidos, backend caído, tiempos de espera, descargas que fallan,
mensajes crípticos, flujos sin salida). Reportar y corregir antes de dar por terminado.
