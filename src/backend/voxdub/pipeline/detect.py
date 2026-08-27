from typing import List, Tuple, Dict, Optional
from .interfaces import Segment, StageResult, StageStatus, validate_segments
from .synthesize import DEFAULT_VOICES


ALLOWED_GENDERS = {"male", "female", "unknown"}


def validate_detection(segments: List[Segment]) -> Tuple[bool, str]:
    """Auditoría de la etapa Detect."""
    if not segments:
        return False, "sin segmentos"
    speakers = set()
    for i, s in enumerate(segments):
        if not s.speaker:
            return False, f"segmento {i}: hablante no asignado"
        speakers.add(s.speaker)
        if s.gender not in ALLOWED_GENDERS:
            return False, f"segmento {i}: genero invalido ({s.gender})"
    if not speakers:
        return False, "ningun hablante"
    return True, f"ok ({len(speakers)} hablantes)"


def assign_default_voices(
    segments: List[Segment], overrides: Dict[str, str] = None
) -> Dict[str, str]:
    """Mapea cada hablante a una voz por su género (override manual del usuario)."""
    overrides = overrides or {}
    mapping: Dict[str, str] = {}
    for s in segments:
        if s.speaker in mapping:
            continue
        mapping[s.speaker] = overrides.get(
            s.speaker, DEFAULT_VOICES.get(s.gender or "unknown", DEFAULT_VOICES["unknown"])
        )
    return mapping


class SpeakerDetector: ...  # Protocol marker


class MockSpeakerDetector:
    """Detector determinista offline: reparte hablantes y género por heurística simple."""

    def __init__(self, n_speakers: int = 2):
        self.n_speakers = n_speakers

    def detect(self, wav_path: str, segments: List[Segment]) -> Tuple[List[Segment], StageResult]:
        for idx, s in enumerate(segments):
            s.speaker = f"spk{idx % self.n_speakers}"
            s.gender = "female" if (idx % self.n_speakers) % 2 == 0 else "male"
        ok, msg = validate_detection(segments)
        status = StageStatus.VERIFIED if ok else StageStatus.FAILED
        mapping = assign_default_voices(segments)
        return segments, StageResult(
            "detect", status,
            details="MockSpeakerDetector",
            metrics={"speakers": len(mapping), "audit": msg, "voices": mapping},
        )


class PyannoteDetector:
    """Adaptador real (lazy). Requiere: pip install pyannote.audio y HF_TOKEN
    (los modelos de diarización de pyannote son gated). Asigna hablantes por
    superposición temporal; el género queda 'unknown' si no hay clasificador de timbre."""

    def __init__(self, hf_token: str = None, n_speakers: int = None):
        self.hf_token = hf_token or os.environ.get("HF_TOKEN")
        self.n_speakers = n_speakers

    def detect(self, wav_path: str, segments: List[Segment]) -> Tuple[List[Segment], StageResult]:
        try:
            from pyannote.audio import Pipeline  # type: ignore
        except ImportError:
            raise RuntimeError(
                "pyannote.audio no instalado. Ejecuta: pip install pyannote.audio"
            )
        if not self.hf_token:
            raise RuntimeError(
                "HF_TOKEN no definido. Los modelos pyannote son gated: "
                "exporta HF_TOKEN=<tu token de huggingface.co> y reintenta."
            )
        try:
            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization@2.1", use_auth_token=self.hf_token
            )
            diar = pipeline(wav_path, min_speakers=1, max_speakers=self.n_speakers)
        except Exception as e:
            raise RuntimeError(f"Diarización falló: {e}")

        turns = []
        for turn, _, spk in diar.itertracks(yield_label=True):
            turns.append((turn.start, turn.end, spk))
        for s in segments:
            mid = (s.start + s.end) / 2.0
            spk = "spk0"
            for (ts, te, label) in turns:
                if ts <= mid <= te:
                    spk = label
                    break
            s.speaker = spk
            s.gender = "unknown"  # sin clasificador de timbre; voz neutrals
        ok, msg = validate_detection(segments)
        status = StageStatus.VERIFIED if ok else StageStatus.FAILED
        mapping = assign_default_voices(segments)
        return segments, StageResult(
            "detect", status,
            details="PyannoteDetector",
            metrics={"speakers": len(mapping), "audit": msg, "voices": mapping},
        )
