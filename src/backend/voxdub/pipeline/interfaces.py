from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    VERIFIED = "verified"
    FAILED = "failed"


@dataclass
class Segment:
    start: float
    end: float
    text: str
    speaker: Optional[str] = None
    gender: Optional[str] = None
    lang: Optional[str] = None
    audio_path: Optional[str] = None
    source_text: Optional[str] = None


@dataclass
class StageResult:
    name: str
    status: StageStatus
    details: str = ""
    metrics: dict = field(default_factory=dict)
    artifacts: dict = field(default_factory=dict)
    engine: str = ""  # "whisper" | "edge-tts" | "mock" | "pyannote" | "wav2lip" | "ffmpeg" | ...

    def health_ok(self) -> bool:
        return self.status == StageStatus.VERIFIED


def validate_segments(segments: List[Segment]) -> (bool, str):
    """Auditoría de salud de una transcripción."""
    if not segments:
        return False, "sin segmentos"
    prev_end = -1.0
    for i, s in enumerate(segments):
        if s.end <= s.start:
            return False, f"segmento {i}: duración no positiva ({s.start}-{s.end})"
        if s.start < 0:
            return False, f"segmento {i}: inicio negativo"
        if s.start < prev_end - 1e-3:
            return False, f"segmento {i}: solapamiento/no ordenado"
        if not s.text or not s.text.strip():
            return False, f"segmento {i}: texto vacío"
        prev_end = s.end
    return True, "ok"
