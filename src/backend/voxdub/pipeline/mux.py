import json
import os
import subprocess

from . import audio

from .interfaces import Segment, StageResult, StageStatus
from . import audio


def validate_mux(out_path: str) -> tuple[bool, str]:
    """Auditoría de la etapa Mux: debe existir y tener streams de video y audio."""
    if not os.path.exists(out_path):
        return False, "archivo no creado"
    if os.path.getsize(out_path) == 0:
        return False, "archivo vacío"
    try:
        probe = subprocess.check_output(
            [audio.resolve_bin("ffprobe"), "-v", "error", "-show_entries",
             "stream=codec_type", "-of", "json", out_path]
        )
        types = [s["codec_type"] for s in json.loads(probe)["streams"]]
    except Exception as e:
        return False, f"ffprobe falló: {e}"
    if "video" not in types:
        return False, "sin stream de video"
    if "audio" not in types:
        return False, "sin stream de audio"
    return True, "ok"


class Muxer:
    """Une el audio sintetizado (por segmento) al video y exporta .mp4 con ffmpeg."""

    def mux(self, video_path: str, segments: list[Segment], out_path: str) -> StageResult:
        audio.ensure_dir(os.path.dirname(out_path) or ".")
        segs = sorted(segments, key=lambda s: s.start)

        list_path = out_path + ".concat.txt"
        with open(list_path, "w") as f:
            for s in segs:
                if s.audio_path and os.path.exists(s.audio_path):
                    f.write(f"file '{os.path.abspath(s.audio_path)}'\n")

        tmp_audio = out_path + ".aac"

        def _run(args):
            p = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            audio.register_proc(p)
            try:
                rc = p.wait()
            finally:
                audio.unregister_proc(p)
            if rc != 0:
                raise subprocess.CalledProcessError(rc, args[0])

        _run([
            audio.resolve_bin("ffmpeg"), "-y", "-f", "concat", "-safe", "0", "-i", list_path,
            "-c:a", "aac", "-b:a", "128k", tmp_audio,
        ])
        _run([
            audio.resolve_bin("ffmpeg"), "-y", "-i", video_path, "-i", tmp_audio,
            "-c:v", "copy", "-c:a", "copy", out_path,
        ])
        ok, msg = validate_mux(out_path)
        status = StageStatus.VERIFIED if ok else StageStatus.FAILED
        return StageResult(
            "mux", status,
            details="ffmpeg mux", metrics={"audit": msg, "out": out_path},
        )
