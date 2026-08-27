import subprocess
import json
import os
import sys
import shutil
import threading


# Registro de subprocesos activos por hilo, para poder cancelarlos (ver JobManager.cancel).
_RUNNING: dict = {}


def register_proc(p: subprocess.Popen):
    _RUNNING[threading.get_ident()] = p


def unregister_proc(p: subprocess.Popen):
    if _RUNNING.get(threading.get_ident()) is p:
        _RUNNING.pop(threading.get_ident(), None)


def kill_proc_for(ident: int):
    p = _RUNNING.get(ident)
    if p is not None and p.poll() is None:
        try:
            p.kill()
        except Exception:
            pass


def resolve_bin(name: str) -> str:
    """Resuelve ffmpeg/ffprobe: env > embebido (MEIPASS/bin) > ./bin > PATH > nombre."""
    env_var = {"ffmpeg": "VOXDUB_FFMPEG", "ffprobe": "VOXDUB_FFPROBE"}.get(name)
    if env_var and os.environ.get(env_var):
        return os.environ.get(env_var)
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        cand = os.path.join(meipass, "bin", name)
        if os.path.exists(cand):
            return cand
    cand = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "bin", name))
    if os.path.exists(cand):
        return cand
    found = shutil.which(name)
    if found:
        return found
    return name


def get_duration(path: str) -> float:
    out = subprocess.check_output(
        [resolve_bin("ffprobe"), "-v", "error", "-show_entries",
         "format=duration", "-of", "json", path]
    )
    return float(json.loads(out)["format"]["duration"])


def extract_audio(video_path: str, out_wav: str, sr: int = 16000) -> str:
    p = subprocess.Popen(
        [resolve_bin("ffmpeg"), "-y", "-i", video_path, "-vn", "-ac", "1",
         "-ar", str(sr), "-f", "wav", out_wav],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    register_proc(p)
    try:
        rc = p.wait()
    finally:
        unregister_proc(p)
    if rc != 0:
        raise subprocess.CalledProcessError(rc, "ffmpeg extract_audio")
    return out_wav


def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path
