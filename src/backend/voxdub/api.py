from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import sys
import shutil

from .jobs import JobManager

app = FastAPI(title="VoxDub API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # en producción restringir al origen de la app
    allow_methods=["*"],
    allow_headers=["*"],
)
jm = JobManager()


@app.get("/capabilities")
def capabilities():
    real_asr = False
    try:
        import faster_whisper  # noqa: F401
        real_asr = True
    except Exception:
        pass
    return {
        "real_asr": real_asr,
        "version": "0.1.0",
    }


@app.post("/jobs")
async def create_job(
    mock: bool = True,
    target_lang: str = "es",
    voice_style: str = "default",
    ai: str = "mock",
    source_lang: str = None,
    burn: bool = False,
    file: UploadFile = File(None),
    path: str = None,
    url: str = None,
):
    """Crea un job. Acepta: archivo (multipart), {path} local o {url} remota.
    ai="free" usa IA gratuita en la nube (traducción MyMemory + TTS edge-tts);
    ai="mock" usa mock local. burn=True quema los subtítulos en el video."""
    video_path = None
    if file is not None:
        name = file.filename or "input.mp4"
        name = os.path.basename(name).replace("/", "_").replace("\\", "_")
        if not name.lower().endswith((".mp4", ".mov", ".mkv", ".webm", ".avi")):
            raise HTTPException(status_code=400, detail="el archivo debe ser video (mp4/mov/mkv/webm/avi)")
        dest = os.path.join(jm.workdir, f"upload_{name}")
        with open(dest, "wb") as f:
            shutil.copyfileobj(file.file, f)
        video_path = dest
    elif path:
        video_path = path
    elif url:
        try:
            from .fetch_video import download_video
            dest = os.path.join(jm.workdir, "url_input.mp4")
            video_path = download_video(url, dest)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"no se pudo descargar el video: {e}")

    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=400, detail="debe enviar 'file', 'path' o 'url' válidos")

    try:
        job = jm.create(video_path, use_mock=mock, target_lang=target_lang, voice_style=voice_style,
                        ai_mode=ai, source_lang=source_lang, burn_subtitles=burn)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"job_id": job.id, "status": job.status}


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = jm.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job no encontrado")
    return job.to_dict()


@app.get("/jobs/{job_id}/download")
def download_job(job_id: str):
    job = jm.get(job_id)
    if not job or job.status != "done":
        raise HTTPException(status_code=404, detail="no disponible")
    return FileResponse(job.out_path, media_type="video/mp4", filename=f"{job_id}.mp4")


class ApplyTranslation(BaseModel):
    overrides: dict


@app.get("/jobs/{job_id}/transcript")
def get_transcript(job_id: str):
    job = jm.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job no encontrado")
    return {"segments": jm.transcript(job_id)}


@app.post("/jobs/{job_id}/apply_translation")
def apply_translation(job_id: str, body: ApplyTranslation):
    ok = jm.apply_translation(job_id, body.overrides)
    if not ok:
        raise HTTPException(status_code=404, detail="job no encontrado o sin transcripción")
    return {"status": "rerendering"}


@app.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    """Cancela un job en curso (p.ej. el usuario subió el video/enlace equivocado)."""
    ok = jm.cancel(job_id)
    if not ok:
        raise HTTPException(status_code=404, detail="job no cancelable (no encontrado o ya terminado)")
    return {"status": "cancelling"}


@app.get("/jobs/{job_id}/subtitles")
def get_subtitles(job_id: str, fmt: str = "srt"):
    job = jm.get(job_id)
    if not job or not job.subtitles:
        raise HTTPException(status_code=404, detail="subtítulos no disponibles")
    path = job.subtitles.get(fmt) or job.subtitles.get("srt")
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="archivo de subtítulos no encontrado")
    media = "application/x-subrip" if fmt == "srt" else "text/vtt"
    return FileResponse(path, media_type=media, filename=f"{job_id}.{fmt}")


LEGAL_TERMS = {
    "title": "Términos de uso y responsabilidad",
    "responsible_use": (
        "El usuario es el ÚNICO responsable del uso que dé a VoxDub. La aplicación "
        "es una herramienta local de traducción y doblaje; quien la usa asume entera "
        "responsabilidad por el contenido procesado y por el cumplimiento de las leyes "
        "y condiciones de las plataformas de origen."
    ),
    "rules": [
        "Procesa únicamente videos de tu propiedad o con autorización expresa del titular.",
        "No clones la voz de personas reales sin su consentimiento; la app usa TTS estándar/generado por IA.",
        "Cumples las leyes de derechos de autor y los ToS de YouTube/TikTok/Instagram/Facebook/etc. al aportar enlaces.",
        "El procesamiento es local; tú decides y respondes por los archivos y URLs que ingresas.",
    ],
    "disclaimer": "VoxDub se entrega 'tal cual', sin garantías. El uso indebido es responsabilidad exclusiva del usuario.",
}


@app.get("/legal")
def legal():
    return LEGAL_TERMS


# Servir el frontend compilado (web/dist) si existe, para un solo comando de app.
def _find_dist():
    candidatos = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidatos.append(os.path.join(meipass, "web", "dist"))
    candidatos.append(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "web", "dist"))
    )
    for c in candidatos:
        if os.path.isdir(c):
            return c
    return None


_DIST = _find_dist()
if _DIST:
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="static")
