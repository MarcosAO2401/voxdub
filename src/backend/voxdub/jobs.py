import os
import shutil
import tempfile
import threading
import uuid
from dataclasses import replace

from .pipeline.orchestrator import Orchestrator


class Job:
    def __init__(self, job_id: str, video_path: str, use_mock: bool, out_path: str):
        self.id = job_id
        self.video_path = video_path
        self.use_mock = use_mock
        self.out_path = out_path
        self.status = "queued"          # queued | running | done | failed
        self.stages = []                # lista de dicts {name,status,details,metrics}
        self.error = None
        self.segments = []              # Segment[] finales (para transcripción editable)
        self.subtitles = None           # {"srt":..., "vtt":...}
        self.warning = None             # aviso no bloqueante (p.ej. video sin voz)
        self.detected_languages = None  # lista de idiomas detectados en el audio
        self.cancelled = False          # cancelación solicitada por el usuario
        self._thread = None             # hilo worker (para matar subprocesos al cancelar)
        self.target_lang = "es"         # idioma destino (para fuente de subtítulos al re-doblar)
        self.ai_mode = "mock"
        self.burn_subtitles = False
        self.source_lang = None

    def to_dict(self):
        return {
            "id": self.id,
            "status": self.status,
            "stages": self.stages,
            "output": self.out_path if self.status == "done" else None,
            "error": self.error,
            "subtitles": self.subtitles,
            "warning": self.warning,
            "detected_languages": self.detected_languages,
            "cancelled": self.cancelled,
        }

    def transcript(self) -> list:
        out = []
        for i, s in enumerate(self.segments):
            out.append({
                "index": i,
                "start": s.start,
                "end": s.end,
                "speaker": s.speaker,
                "gender": s.gender,
                "source": s.source_text or s.text,
                "target": s.text,
            })
        return out


class JobManager:
    """Cola de jobs en memoria con ejecución en hilo y auditoría por etapa."""

    def __init__(self, workdir: str = None):
        workdir = workdir or os.path.join(tempfile.gettempdir(), "voxdub_jobs")
        os.makedirs(workdir, exist_ok=True)
        self.workdir = workdir
        self.jobs = {}
        self._lock = threading.Lock()

    def create(self, video_path: str, use_mock: bool = True,
                target_lang: str = "es", voice_style: str = "default",
                ai_mode: str = "mock", source_lang: str = None,
                burn_subtitles: bool = False) -> Job:
        with self._lock:
            # Un solo job activo a la vez (evita cargar varios Whisper y OOM).
            for j in self.jobs.values():
                if j.status in ("queued", "running"):
                    raise RuntimeError("Ya hay un video procesándose; espera a que termine.")
            # Liberar disco: eliminar workdirs de jobs ya finalizados.
            for jid, j in list(self.jobs.items()):
                if j.status in ("done", "failed"):
                    shutil.rmtree(os.path.join(self.workdir, jid), ignore_errors=True)
                    self.jobs.pop(jid, None)
        job_id = uuid.uuid4().hex[:12]
        out_path = os.path.join(self.workdir, f"{job_id}.mp4")
        job = Job(job_id, video_path, use_mock, out_path)
        job.ai_mode = ai_mode
        job.burn_subtitles = burn_subtitles
        job.source_lang = source_lang
        job.target_lang = target_lang
        with self._lock:
            self.jobs[job_id] = job
        t = threading.Thread(
            target=self._run,
            args=(job, target_lang, voice_style, ai_mode, source_lang, burn_subtitles),
            daemon=True,
        )
        job._thread = t
        t.start()
        return job

    def cancel(self, job_id: str) -> bool:
        """Cancela un job en curso. Detiene el pipeline entre etapas y mata el ffmpeg activo."""
        job = self.jobs.get(job_id)
        if not job or job.status not in ("queued", "running"):
            return False
        job.cancelled = True
        if job._thread is not None:
            try:
                from .pipeline import audio
                audio.kill_proc_for(job._thread.ident)
            except Exception:
                pass
        return True

    def _run(self, job: Job, target_lang: str, voice_style: str = "default",
             ai_mode: str = "mock", source_lang: str = None, burn_subtitles: bool = False):
        job.status = "running"
        overrides = {"*": voice_style} if voice_style and voice_style != "default" else None
        try:
            orch = Orchestrator(workdir=os.path.join(self.workdir, job.id))
            segs, results, extras = orch.run_staged(
                job.video_path, use_mock=job.use_mock,
                target_lang=target_lang, out_path=job.out_path,
                overrides=overrides, ai_mode=ai_mode,
                burn_subtitles=burn_subtitles, source_lang=source_lang,
                asr_lang=source_lang, cancelled=lambda: job.cancelled,
            )
            if job.cancelled:
                job.status = "failed"
                job.error = "cancelado por el usuario"
                return
            for name, res in results:
                job.stages.append({
                    "name": name,
                    "status": res.status.value,
                    "details": res.details,
                    "metrics": res.metrics,
                })
            job.segments = segs
            job.subtitles = extras.get("subtitles")
            job.warning = extras.get("warning")
            job.detected_languages = extras.get("detected_languages")
            if job.stages and job.stages[-1]["status"] == "verified":
                job.status = "done"
            else:
                job.status = "failed"
                job.error = "auditoria: alguna etapa no verificada"
        except Exception as e:  # nunca dejar el job colgado
            job.status = "failed"
            job.error = "cancelado por el usuario" if job.cancelled else str(e)

    def get(self, job_id: str) -> Job:
        return self.jobs.get(job_id)

    def transcript(self, job_id: str) -> list:
        job = self.jobs.get(job_id)
        if not job:
            return []
        return job.transcript()

    def apply_translation(self, job_id: str, overrides: dict) -> bool:
        """Re-dobla con el texto traducido corregido (paridad: revisar y editar).
        overrides: {indice: nuevo_texto}."""
        job = self.jobs.get(job_id)
        if not job or not job.segments:
            return False
        new_segs = []
        for i, s in enumerate(job.segments):
            ns = replace(s)
            key = str(i)
            if key in overrides and overrides[key]:
                ns.text = overrides[key]
            new_segs.append(ns)
        job.status = "running"
        t = threading.Thread(target=self._rerender, args=(job, new_segs), daemon=True)
        t.start()
        return True

    def _rerender(self, job: Job, new_segs: list):
        out_v2 = job.out_path + ".v2.mp4"
        try:
            orch = Orchestrator(workdir=os.path.join(self.workdir, job.id))
            segs, res, extras = orch.rerender(
                job.video_path, new_segs, out_v2,
                use_mock=job.use_mock, ai_mode=job.ai_mode,
                burn_subtitles=job.burn_subtitles, cancelled=lambda: job.cancelled,
                target_lang=job.target_lang,
            )
            if job.cancelled:
                job.status = "failed"
                job.error = "cancelado por el usuario"
                return
            if res.status.value == "verified":
                job.out_path = out_v2
                job.segments = segs
                job.subtitles = extras.get("subtitles")
                job.warning = extras.get("warning")
                job.detected_languages = extras.get("detected_languages")
                job.status = "done"
            else:
                job.status = "failed"
                job.error = "re-doblaje: etapa no verificada"
        except Exception as e:
            job.status = "failed"
            job.error = str(e)
