import json
import os
import subprocess

from . import audio

from .interfaces import Segment, StageResult, StageStatus
from . import audio


def validate_lipsync(out_path: str) -> tuple[bool, str]:
    """Auditoría de lip-sync: debe existir y tener stream de video."""
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
    return True, "ok"


class Lipsync:
    """Protocol marker."""


class MockLipsync:
    """Lip-sync offline: copia el video (el warp real lo hace Wav2Lip en producción)."""

    def sync(self, video_path: str, segments: list[Segment], out_path: str) -> StageResult:
        audio.ensure_dir(os.path.dirname(out_path) or ".")
        # El mock no reesculpe la boca; entrega el video para que el mux luego
        # incruste el audio sintetizado. La auditoría verifica que el video existe.
        subprocess.check_call([
            audio.resolve_bin("ffmpeg"), "-y", "-i", video_path, "-c", "copy", out_path,
        ])
        ok, msg = validate_lipsync(out_path)
        status = StageStatus.VERIFIED if ok else StageStatus.FAILED
        return StageResult(
            "lipsync", status,
            details="MockLipsync (copia de video; warp real en Wav2Lip)",
            metrics={"audit": msg, "video": out_path},
            artifacts={"video_path": out_path},
        )


class Wav2LipLipsync:
    """Adaptador real: ejecuta la inferencia de Wav2Lip (deep learning) vía el repo clonado.
    Requiere:
      - WAV2LIP_REPO: ruta al repo https://github.com/Rudrabha/Wav2Lip clonado
      - WAV2LIP_CKPT: ruta al checkpoint (wav2lip.pth / wav2lip_gan.pth)
    Une el audio sintetizado (por segmento) y warpea la boca al video."""

    def sync(self, video_path: str, segments: list[Segment], out_path: str) -> StageResult:
        import tempfile
        repo = os.environ.get("WAV2LIP_REPO")
        ckpt = os.environ.get("WAV2LIP_CKPT")
        if not repo:
            raise RuntimeError(
                "Wav2Lip no configurado. Define WAV2LIP_REPO al repo clonado "
                "(https://github.com/Rudrabha/Wav2Lip) y WAV2LIP_CKPT a los pesos. "
                "Ejecuta: python scripts/setup_models.py. Mientras tanto, el modo mock copia el video."
            )
        if not ckpt:
            # Autolocalizar el checkpoint dentro del repo (checkpoints/ o raíz).
            cand = [
                os.path.join(repo, "checkpoints", "wav2lip_gan.pth"),
                os.path.join(repo, "wav2lip_gan.pth"),
                os.path.join(repo, "checkpoints", "wav2lip.pth"),
            ]
            for c in cand:
                if os.path.exists(c):
                    ckpt = c
                    break
        if not ckpt or not os.path.exists(ckpt):
            raise RuntimeError(f"Wav2Lip: checkpoint no encontrado en {ckpt or '(vacío)'}. "
                               f"Define WAV2LIP_CKPT o colócalo en {repo}/checkpoints/wav2lip_gan.pth")
        audio.ensure_dir(os.path.dirname(out_path) or ".")
        # Concatenar el audio sintetizado en una pista única.
        tmpdir = tempfile.mkdtemp(prefix="voxdub_lip_")
        concat_list = os.path.join(tmpdir, "list.txt")
        full_audio = os.path.join(tmpdir, "full.wav")
        with open(concat_list, "w") as f:
            for s in sorted(segments, key=lambda x: x.start):
                if getattr(s, "audio_path", None) and os.path.exists(s.audio_path):
                    f.write(f"file '{os.path.abspath(s.audio_path)}'\n")
        subprocess.check_call([
            audio.resolve_bin("ffmpeg"), "-y", "-f", "concat", "-safe", "0",
            "-i", concat_list, "-c", "copy", full_audio,
        ])
        try:
            subprocess.check_call([
                "python", os.path.join(repo, "inference.py"),
                "--checkpoint_path", ckpt,
                "--face", video_path,
                "--audio", full_audio,
                "--outfile", out_path,
                "--static", "False", "--nosmooth", "True",
            ])
        except Exception as e:
            raise RuntimeError(f"Inferencia Wav2Lip falló: {e}")
        ok, msg = validate_lipsync(out_path)
        status = StageStatus.VERIFIED if ok else StageStatus.FAILED
        return StageResult(
            "lipsync", status,
            details="Wav2LipLipsync (inferencia real)",
            metrics={"audit": msg, "video": out_path},
            artifacts={"video_path": out_path},
        )
