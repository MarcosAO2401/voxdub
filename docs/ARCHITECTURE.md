# Arquitectura — VoxDub

## Pipeline (etapas desacopladas)
```
video ─▶ audio (ffmpeg)
  ─▶ Transcribe   (Whisper)            → segmentos + timestamps
  ─▶ Detect       (pyannote)           → hablantes + género (probabilístico)
  ─▶ Translate    (MT/LLM local)       → texto traducido alineado
  ─▶ Synthesize   (TTS: Piper/Coqui)   → audio por hablante/género + override
  ─▶ Mux          (ffmpeg + Wav2Lip?)  → .mp4 doblado
```
Cada etapa implementa la interfaz `Stage` y devuelve `StageResult` con `status`
(`pending|running|verified|failed`), `metrics` y `artifacts`. El `Orchestrator`
corre las etapas y aplica la **puerta de auditoría** antes de avanzar.

## Estado por fase
- Fase 1 (Transcribe): ✅ implementada + smoke test.
- Fase 2 (Detect género/hablante + voz por defecto): ✅ implementada + smoke test.
- Fase 3 (Translate): ✅ implementada + smoke test.
- Fase 4 (Synthesize): ✅ implementada + smoke test. `MockSynthesizer` (offline) + `PiperSynthesizer` (real, `piper-tts` ya instalado y verificado). Voces en `voices/` con `manifest.json` y descarga segura (`scripts/fetch_voice.py`).
- Fase 5 (Mux): ✅ implementada + smoke test. `Muxer` real con ffmpeg (concatena audio por segmento y exporta `.mp4` con video+audio verificados). Pipeline end-to-end funcional.
- **Lip-sync (IA, Wav2Lip)**: ✅ etapa `lipsync.py` implementada + smoke test. `MockLipsync` (offline, copia de video) + `Wav2LipLipsync` (adaptador real, lazy). Va entre synthesize y mux; warpea la boca al audio nuevo. Pipeline = transcribe→detect→translate→synthesize→**lipsync**→mux (6 etapas auditadas).
- Fase 6 (Backend API): ✅ implementada + smoke test. FastAPI (`api.py`, CORS habilitado) + `JobManager` (cola en hilo con auditoría por etapa) + `server.py` (uvicorn). `pip install fastapi uvicorn` ya verificado. Endpoints: `POST /jobs` (upload o path), `GET /jobs/{id}`, `GET /jobs/{id}/download`.
- Fase 7 (Frontend): ✅ scaffold React+Vite+Tailwind compila (`npm install` + `npm run build` OK) y está **conectado a la API** (`App.tsx`: sube video, elige idioma y estilo de voz, muestra la cinta de auditoría en vivo por etapa y descarga el `.mp4`).
- **Binario autónomo (sidecar Tauri)**: ✅ `scripts/build_backend.py` empaqueta la API + frontend compilado **y `ffmpeg`/`ffprobe`** en un onefile (`dist_backend/voxdub-backend`, ~130 MB) verificado end-to-end: sirve `GET /` (HTML), la API y completa las 6 etapas (`verified`) con el `.mp4` de salida. `audio.resolve_bin()` busca ffmpeg en: env `VOXDUB_FFMPEG` → embebido (`MEIPASS/bin`) → `./bin` → `PATH`. `scripts/prepare_tauri_sidecar.sh` copia el binario a `web/src-tauri/binaries/voxdub-backend-<triple>` y `main.rs` lo lanza con `tauri-plugin-shell`. Resultado: un `.exe`/`.app` **totalmente self-contained** (sin depender de ffmpeg del sistema). Para otra plataforma, reemplazar `bin/ffmpeg` y `bin/ffprobe` por un build estático de esa plataforma antes de compilar. Requiere `npm run tauri:build` en tu máquina (Rust + webkit2gtk).

## Entrada por URL (modo enlace)
- ✅ implementada + smoke test (`test_url_smoke`). El backend acepta `url` en `POST /jobs`: descarga el video (HTTP directo vía stdlib; plataformas YouTube/TikTok/etc. si `yt-dlp` está instalado) y corre el mismo pipeline de 6 etapas.
- Frontend: toggle **Subir archivo / Desde enlace**; en modo enlace envía `?url=...`.
- **Salvedad legal:** solo URLs de contenido propio o autorizado (coherente con `AGENTS.md`). Descargar de terceros puede violar sus ToS; el usuario es responsable.

## Términos de uso / responsabilidad legal
- ✅ implementado: endpoint `GET /legal` (texto de términos), modal **Términos de uso** en el frontend (botón en la cabecera, con aceptación persistida en `localStorage`) y `LEGAL.md`.
- El usuario acepta ser el único responsable del uso (contenido autorizado, sin clonar voces reales, cumplir ToS de plataformas).

## Paridad con HeyGen / ElevenLabs / Rask AI
La app ya cubre el flujo núcleo (transcribir → hablantes/género → traducir → TTS por género → lip-sync → mux) **más**:
- **Subtítulos** (SRT/VTT) generados del audio doblado y descargables (`GET /jobs/{id}/subtitles`).
- **Transcripción editable**: `GET /transcript` muestra original+traducido; `POST /apply_translation` re-dobla con el texto corregido (revisar y editar antes de doblar, como HeyGen/Rask).
Para igualar esas plataformas falta activar **modelos reales** (Whisper, NLLB, Piper/Coqui, Wav2Lip) — todo cableado con adaptadores lazy. La **voz clonada de personas reales quedó fuera de alcance por diseño** (regla del usuario: solo TTS estándar/generado por IA). Una librería de voces más rica (cargar `voices/manifest.json`) es un pendiente menor.

## IA ya integrada (no es un añadido opcional)
La app **es** un sistema de IA: ASR (Whisper), diarización+género (pyannote), traducción (NLLB/transformers), TTS (Piper), y lip-sync (Wav2Lip, deep learning). Los adaptadores reales usan lazy import; los *mock* son solo placeholders offline para desarrollo/auditoría. Cuando instalas `requirements.txt` y bajas los pesos (con `scripts/fetch_voice.py`, verificado por SHA256), el pipeline pasa de mock a modelos reales sin tocar código.

## Design System (estética "studio tool")
- Dark-first. Tokens: bg `#0E0F13`, surface `#171922`, border `#262A36`,
  accent `#5B8DEF` (índigo) o `#3DDC97` (verde). Texto `#E6E8EC` / mutado `#8A90A2`.
- Tipografía: Inter (UI) / JetBrains Mono (logs). Radios 10–12px, sombras suaves.
- Layout 3 zonas: preview centro · timeline hablantes izq · panel voces/ajustes der.
- **Cinta de pipeline** arriba: cada etapa con estado en vivo
  (`⧗ pendiente · ▶ ejecutando · ✓ verificado · ✗ falló`) — hace visible la regla de auditoría.
- Estados vacíos/error/loading diseñados; modo claro opcional; accesibilidad AA.

## Stack
- Backend: Python 3.11+, FastAPI, ffmpeg (CLI), whisper/pyannote/piper (opcionales).
- Frontend: React + Vite + Tailwind; empaquetado Tauri (binario <50MB).
- Tests: unittest (smoke) + pipeline dorado en CI.
