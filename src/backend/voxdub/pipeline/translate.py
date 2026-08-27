from typing import List, Tuple, Protocol
import json
import urllib.parse
import urllib.request
from .interfaces import Segment, StageResult, StageStatus, validate_segments


def validate_translation(segments: List[Segment]) -> Tuple[bool, str]:
    """Auditoría de la etapa Translate. Los segmentos vacíos (silencio/sin voz) se permiten."""
    if not segments:
        return False, "sin segmentos"
    for i, s in enumerate(segments):
        if not s.text or not s.text.strip():
            continue
        if not s.lang:
            return False, f"segmento {i}: idioma destino no fijado"
    return True, "ok"


class Translator(Protocol):
    def translate(self, segments: List[Segment]) -> Tuple[List[Segment], StageResult]: ...


class MockTranslator:
    """Traductor determinista offline (marcador de traducción, sin red)."""

    def __init__(self, target_lang: str = "es"):
        self.target_lang = target_lang

    def translate(self, segments: List[Segment]) -> Tuple[List[Segment], StageResult]:
        for s in segments:
            s.source_text = s.text
            s.text = f"{s.text} [traducido→{self.target_lang}]"
            s.lang = self.target_lang
        ok, msg = validate_translation(segments)
        status = StageStatus.VERIFIED if ok else StageStatus.FAILED
        return segments, StageResult(
            "translate", status, engine="mock",
            details=f"MockTranslator:{self.target_lang}",
            metrics={"segments": len(segments), "audit": msg},
        )


class NLLBTranslator:
    """Adaptador real (lazy). Requiere: pip install transformers sentencepiece."""

    def __init__(self, target_lang: str = "spa_Latn"):
        self.target_lang = target_lang

    def translate(self, segments: List[Segment]) -> Tuple[List[Segment], StageResult]:
        try:
            import transformers  # type: ignore
        except ImportError:
            raise RuntimeError(
                "transformers no instalado. Ejecuta: pip install transformers sentencepiece"
            )
        # TODO: cargar NLLB y traducir cada segmento; fijar s.lang.
        raise NotImplementedError("NLLBTranslator pendiente de cargar modelo y tokenizer")


def _source_for(target_lang: str) -> str:
    # MyMemory necesita el par lengua origen|destino. Sin detector automático fiable
    # y gratuito, usamos un heurístico: si el destino es español, asumimos origen inglés.
    return "en" if target_lang == "es" else "es"


class FreeTranslator:
    """Traductor gratuito y sin clave vía MyMemory (nube). No requiere API key.
    Conecta a internet; si falla, lanza para que la etapa quede FAILED y el
    usuario pueda volver al modo mock/local."""

    ENDPOINT = "https://api.mymemory.translated.net/get"

    def __init__(self, target_lang: str = "es", source_lang: str = None):
        self.target_lang = target_lang
        self.source_lang = source_lang or _source_for(target_lang)

    def _translate_one(self, text: str, source_lang: str) -> str:
        q = urllib.parse.quote(text)
        url = f"{self.ENDPOINT}?q={q}&langpair={source_lang}|{self.target_lang}"
        last = None
        for _ in range(3):
            try:
                with urllib.request.urlopen(url, timeout=15) as r:
                    data = json.loads(r.read())
                return data["responseData"]["translatedText"]
            except Exception as e:
                last = e
        raise last or RuntimeError("MyMemory no respondió")

    def translate(self, segments: List[Segment]) -> Tuple[List[Segment], StageResult]:
        out = []
        for s in segments:
            s.source_text = s.text
            # Idioma origen: el detectado por segmento, si no el global, si no heurístico.
            src = s.lang or self.source_lang or _source_for(self.target_lang)
            try:
                s.text = self._translate_one(s.text, src)
            except Exception as e:
                return segments, StageResult(
                    "translate", StageStatus.FAILED,
                    details=f"FreeTranslator(MyMemory) falló: {e}",
                )
            s.lang = self.target_lang
            out.append(s)
        ok, msg = validate_translation(out)
        status = StageStatus.VERIFIED if ok else StageStatus.FAILED
        return out, StageResult(
            "translate", status, engine="mymemory",
            details=f"FreeTranslator(MyMemory):{self.source_lang}->{self.target_lang}",
            metrics={"segments": len(out), "audit": msg},
        )
