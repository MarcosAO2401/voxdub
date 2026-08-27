import json
import os
import subprocess
import asyncio
from typing import List, Tuple, Dict, Optional

from .interfaces import Segment, StageResult, StageStatus, validate_segments
from . import audio


DEFAULT_VOICES = {
    "female": "ia-voice-female-01",
    "male": "ia-voice-male-01",
    "unknown": "ia-voice-neutral-01",
}


def validate_synthesis(segments: List[Segment]) -> Tuple[bool, str]:
    """Auditoría de la etapa Synthesize: cada segmento debe tener audio real."""
    if not segments:
        return False, "sin segmentos"
    for i, s in enumerate(segments):
        if not s.audio_path or not os.path.exists(s.audio_path):
            return False, f"segmento {i}: audio no generado"
        if os.path.getsize(s.audio_path) == 0:
            return False, f"segmento {i}: audio vacío"
    return True, "ok"


def load_voice_manifest(voice_dir: str) -> Dict[str, dict]:
    """Carga el archivo de voces IA (manifest.json) de la carpeta de voces."""
    manifest = os.path.join(voice_dir, "manifest.json")
    if not os.path.exists(manifest):
        return {}
    with open(manifest) as f:
        data = json.load(f)
    return data.get("voices", {})


def resolve_voice(speaker: str, gender: str, overrides: Dict[str, str],
                  manifest: Dict[str, dict]) -> str:
    """Elige la voz: override global "*" > override por speaker > género > neutral."""
    if "*" in overrides:
        return overrides["*"]
    if speaker in overrides:
        return overrides[speaker]
    if gender in manifest:
        return gender  # clave en el manifest por género
    return "neutral"


class Synthesizer:
    """Protocol marker."""


class MockSynthesizer:
    """Sintetiza WAVs silenciosos de la duración correcta (offline, verificable)."""

    def __init__(self, workdir: str, overrides: Dict[str, str] = None,
                 voice_dir: str = "voices"):
        self.workdir = audio.ensure_dir(workdir)
        self.overrides = overrides or {}
        self.manifest = load_voice_manifest(voice_dir)

    def synthesize(self, segments: List[Segment]) -> Tuple[List[Segment], StageResult]:
        audio.ensure_dir(os.path.join(self.workdir, "seg"))
        for i, s in enumerate(segments):
            dur = max(0.1, round(s.end - s.start, 3))
            out = os.path.join(self.workdir, "seg", f"seg_{i}.wav")
            # WAV silencioso de la duración del segmento (placeholder de TTS real)
            subprocess_silent(out, dur)
            s.audio_path = out
            voice = resolve_voice(s.speaker or "spk?", s.gender or "unknown",
                                 self.overrides, self.manifest)
            s.text = f"[{voice}] {s.text}"
        ok, msg = validate_synthesis(segments)
        status = StageStatus.VERIFIED if ok else StageStatus.FAILED
        return segments, StageResult(
            "synthesize", status,
            details="MockSynthesizer (WAV silencioso)",
            metrics={"segments": len(segments), "audit": msg},
        )


def subprocess_silent(out_path: str, dur: float):
    import subprocess
    from . import audio
    subprocess.check_call([
        audio.resolve_bin("ffmpeg"), "-y", "-f", "lavfi", "-i", f"anullsrc=d={dur}",
        "-t", str(dur), "-ac", "1", "-ar", "22050", out_path,
    ])


# Voces gratuitas de Microsoft Edge TTS (sin clave, vía edge-tts). Mapeo por idioma+género.
EDGE_VOICES = {
    "es": {"female": "es-MX-DaliaNeural", "male": "es-ES-AlvaroNeural"},
    "en": {"female": "en-US-AriaNeural", "male": "en-US-GuyNeural"},
    "fr": {"female": "fr-FR-DeniseNeural", "male": "fr-FR-HenriNeural"},
    "de": {"female": "de-DE-KatjaNeural", "male": "de-DE-ConradNeural"},
    "it": {"female": "it-IT-ElsaNeural", "male": "it-IT-DiegoNeural"},
    "pt": {"female": "pt-BR-FranciscaNeural", "male": "pt-BR-AntonioNeural"},
    "ru": {"female": "ru-RU-SvetlanaNeural", "male": "ru-RU-DmitryNeural"},
    "ja": {"female": "ja-JP-NanamiNeural", "male": "ja-JP-KeitaNeural"},
    "zh": {"female": "zh-CN-XiaoxiaoNeural", "male": "zh-CN-YunxiNeural"},
    "ko": {"female": "ko-KR-SunHiNeural", "male": "ko-KR-InJoonNeural"},
    "ar": {"female": "ar-SA-ZariyahNeural", "male": "ar-SA-HamedNeural"},
}


class EdgeTTSSynthesizer:
    """TTS real y gratuito en la nube vía edge-tts (sin API key). Requiere red.
    Conecta a internet; si falla, la etapa queda FAILED y el usuario puede usar mock."""

    def __init__(self, workdir: str, lang: str = "es", overrides: Dict[str, str] = None):
        self.workdir = audio.ensure_dir(workdir)
        self.lang = lang
        self.overrides = overrides or {}

    def _voice_for(self, gender: str) -> str:
        g = "male" if (gender or "").lower() == "male" else "female"
        return EDGE_VOICES.get(self.lang, EDGE_VOICES["es"])[g]

    async def _synth(self, segments: List[Segment]):
        import edge_tts  # lazy: solo si se usa modo libre
        ctx = self.overrides.get("*") or ""
        for i, s in enumerate(segments):
            text = (s.text or "").strip()
            mp3 = os.path.join(self.workdir, "seg", f"seg_{i}.mp3")
            wav = os.path.join(self.workdir, "seg", f"seg_{i}.wav")
            # Un video sin voz (segmento vacío) no debe romper todo el doblaje.
            if not text:
                subprocess_silent(wav, max(0.1, round(s.end - s.start, 3)))
                s.audio_path = wav
                continue
            voice = ctx if ctx else self._voice_for(s.gender)
            last_err = None
            for _ in range(3):  # reintento ante errores de red transitorios
                try:
                    comm = edge_tts.Communicate(text, voice)
                    await comm.save(mp3)
                    break
                except Exception as e:  # noqa: BLE001
                    last_err = e
            else:
                raise last_err or RuntimeError("edge-tts falló")
            subprocess.check_call([
                audio.resolve_bin("ffmpeg"), "-y", "-i", mp3,
                "-ac", "1", "-ar", "22050", wav,
            ])
            s.audio_path = wav

    def synthesize(self, segments: List[Segment]) -> Tuple[List[Segment], StageResult]:
        audio.ensure_dir(os.path.join(self.workdir, "seg"))
        try:
            asyncio.run(self._synth(segments))
        except Exception as e:
            return segments, StageResult(
                "synthesize", StageStatus.FAILED,
                details=f"EdgeTTS falló: {e}",
            )
        ok, msg = validate_synthesis(segments)
        status = StageStatus.VERIFIED if ok else StageStatus.FAILED
        return segments, StageResult(
            "synthesize", status,
            details="EdgeTTSSynthesizer (nube gratuita)",
            metrics={"segments": len(segments), "audit": msg},
        )


class PiperSynthesizer:
    """Adaptador real (lazy). Requiere: pip install piper-tts + voces .onnx."""

    def __init__(self, workdir: str, voice_dir: str = "voices",
                 overrides: Dict[str, str] = None):
        self.workdir = audio.ensure_dir(workdir)
        self.voice_dir = voice_dir
        self.overrides = overrides or {}
        self.manifest = load_voice_manifest(voice_dir)

    def synthesize(self, segments: List[Segment]) -> Tuple[List[Segment], StageResult]:
        try:
            from piper import PiperVoice  # type: ignore
        except ImportError:
            raise RuntimeError(
                "piper-tts no instalado. Ejecuta: pip install piper-tts "
                "y descarga voces desde https://github.com/rhasspy/piper"
            )
        audio.ensure_dir(os.path.join(self.workdir, "seg"))
        loaded: dict = {}
        for i, s in enumerate(segments):
            voice_key = resolve_voice(s.speaker or "spk?", s.gender or "unknown",
                                      self.overrides, self.manifest)
            model_path = os.path.join(self.voice_dir, f"{voice_key}.onnx")
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"Voz no encontrada: {model_path}")
            if model_path not in loaded:
                loaded[model_path] = PiperVoice.load(model_path)
            voice = loaded[model_path]
            out = os.path.join(self.workdir, "seg", f"seg_{i}.wav")
            with open(out, "wb") as f:
                voice.synthesize(s.text, f)
            s.audio_path = out
        ok, msg = validate_synthesis(segments)
        status = StageStatus.VERIFIED if ok else StageStatus.FAILED
        return segments, StageResult(
            "synthesize", status,
            details="PiperSynthesizer", metrics={"audit": msg},
        )
