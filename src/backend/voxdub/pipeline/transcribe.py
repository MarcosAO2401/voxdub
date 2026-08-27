from typing import List, Tuple, Protocol
import threading
from .interfaces import Segment, StageResult, StageStatus, validate_segments
from . import audio


_MODEL_CACHE: dict = {}
_MODEL_LOCK = threading.Lock()


def _get_model(model_name: str, device: str, compute_type: str):
    """Cache de modelos a nivel de proceso (los jobs se serializan a 1, así es seguro)."""
    key = (model_name, device, compute_type)
    with _MODEL_LOCK:
        if key not in _MODEL_CACHE:
            from faster_whisper import WhisperModel
            _MODEL_CACHE[key] = WhisperModel(model_name, device=device, compute_type=compute_type)
        return _MODEL_CACHE[key]


class Transcriber(Protocol):
    def transcribe(self, wav_path: str) -> Tuple[List[Segment], StageResult]: ...


class MockTranscriber:
    """Transcriptor determinista para smoke tests (no requiere modelos)."""

    def __init__(self, segments: List[Segment] = None):
        self._segments = segments

    def transcribe(self, wav_path: str) -> Tuple[List[Segment], StageResult]:
        dur = audio.get_duration(wav_path)
        if self._segments:
            segs = self._segments
        else:
            segs = [Segment(0.0, round(dur, 3), "transcripcion de ejemplo (mock)")]
        ok, msg = validate_segments(segs)
        status = StageStatus.VERIFIED if ok else StageStatus.FAILED
        return segs, StageResult(
            "transcribe", status, engine="mock",
            details="MockTranscriber",
            metrics={"segments": len(segs), "duration": dur, "audit": msg},
        )


class WhisperTranscriber:
    """Adaptador real con faster-whisper (ctranslate2, sin torch pesado).
    Requiere: pip install faster-whisper. El modelo se descarga solo la primera vez.
    Detecta el idioma hablado por segmento (soporta varios idiomas en un mismo video)."""

    def __init__(self, model_name: str = "base", language: str = None, device: str = "auto",
                 cancelled: "callable" = None):
        self.model_name = model_name
        self.language = language  # None = autodetectar por segmento
        self.device = device
        self.cancelled = cancelled
        self._model = None

    def _load(self):
        self._model = _get_model(self.model_name, self.device, "int8")

    def transcribe(self, wav_path: str) -> Tuple[List[Segment], StageResult]:
        try:
            if self._model is None:
                self._load()
        except Exception as e:
            raise RuntimeError(f"Whisper (faster-whisper) no disponible: {e}")

        def _cb(seg, info):  # faster-whisper aborta si devolvemos False
            if self.cancelled and self.cancelled():
                return False
            return None

        segs_out, info = self._model.transcribe(
            wav_path, language=self.language, word_timestamps=False, beam_size=5,
            callback=_cb if self.cancelled else None,
        )
        segs = [
            Segment(round(s.start, 3), round(s.end, 3), s.text.strip())
            for s in segs_out if s.text and s.text.strip()
        ]
        detected: set = set()
        # Caso "sin voz": no romper el pipeline; se entrega como VERIFIED + aviso.
        if not segs:
            dur = round(audio.get_duration(wav_path), 3)
            segs = [Segment(0.0, dur, "")]
            return segs, StageResult(
                "transcribe", StageStatus.VERIFIED, engine="whisper",
                details=f"whisper:{self.model_name} (sin voz detectada)",
                metrics={"segments": 0, "audit": "sin voz"},
            )
        # Detección de idioma por segmento (multi-idioma en un mismo video).
        if not self.language:
            try:
                from faster_whisper.audio import load_audio
                arr = load_audio(wav_path, sr=16000)
                sr = 16000
                for s in segs:
                    if s.end - s.start >= 1.0:
                        a = arr[int(s.start * sr):int(s.end * sr)]
                        if len(a) >= sr:
                            try:
                                lang, _ = self._model.detect_language(a)
                                s.lang = lang
                                detected.add(lang)
                            except Exception:
                                pass
            except Exception:
                pass
            # Rellenar huecos con el idioma global detectado por Whisper.
            global_lang = getattr(info, "language", None)
            if global_lang:
                detected.add(global_lang)
                for s in segs:
                    if not s.lang:
                        s.lang = global_lang
        return segs, StageResult(
            "transcribe", StageStatus.VERIFIED, engine="whisper",
            details=f"whisper:{self.model_name}",
            metrics={
                "segments": len(segs),
                "detected_languages": sorted(detected),
                "audit": "ok",
            },
        )
