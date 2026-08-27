# VoxDub

Traductor/doblador de video **local**. Pipeline: transcribir → detectar hablantes/género
→ traducir → sintetizar voz (TTS estándar por género + override) → exportar `.mp4`.

- **Fase 1 (Transcribe)** implementada y verificable offline con `MockTranscriber`.
- Regla de ingeniería: **auditar antes de avanzar** (smoke test verde por etapa).

## Uso rápido (backend)
```bash
# Auditar Fase 1 sobre un video propio (mock, sin modelos)
PYTHONPATH=src/backend python -m voxdub.cli transcribe tu_video.mp4 --mock

# Pipeline completo Fase 1..4 (mock, offline, genera WAVs reales silenciosos)
PYTHONPATH=src/backend python -m voxdub.cli synthesize tu_video.mp4 --mock

# Pipeline COMPLETO Fase 1..5 → exporta .mp4 doblado (mux real con ffmpeg)
PYTHONPATH=src/backend python -m voxdub.cli build tu_video.mp4 --mock --out out.mp4

# Smoke tests (todas las fases)
PYTHONPATH=src/backend python -m unittest discover -s tests
```

## Hacerlo totalmente funcional (modelos reales)
`piper-tts` ya está instalado y verificado. Para voz real:
```bash
python scripts/fetch_voice.py --name es_ES-carlfm-low --url <URL_directa_.onnx> --sha256 <hash>
```
Las demás fases usan adaptadores reales con lazy import; instala según
`requirements.txt` (`pip install -r requirements.txt`) en tu entorno de desarrollo.

## Seguridad / legal
- Solo contenido propio o autorizado; cero red por defecto.
- Los pesos de voz se descargan con verificación SHA256 (supply-chain safe).
- No se clona la voz de personas reales; solo TTS estándar/generado por IA.

## Frontend (scaffold)
```bash
cd web && npm install && npm run dev
```

## Servicio (Fase 6)
```bash
# Instalar (ya verificado en este entorno)
pip install fastapi uvicorn
# Levantar API
PYTHONPATH=src/backend python -m voxdub.server
# Usar
curl -X POST "http://127.0.0.1:8000/jobs?mock=true&path=tu_video.mp4"
curl "http://127.0.0.1:8000/jobs/<job_id>"      # estado por etapa (auditoría)
curl "http://127.0.0.1:8000/jobs/<job_id>/download"  # descarga el .mp4
```
