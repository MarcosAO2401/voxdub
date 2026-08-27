import os
from .interfaces import StageResult, StageStatus
from .transcribe import Transcriber, MockTranscriber, WhisperTranscriber
from .detect import SpeakerDetector, MockSpeakerDetector, PyannoteDetector, validate_detection
from .translate import Translator, MockTranslator, NLLBTranslator, FreeTranslator, validate_translation
from .synthesize import Synthesizer, MockSynthesizer, PiperSynthesizer, EdgeTTSSynthesizer, validate_synthesis
from .lipsync import Lipsync, MockLipsync, Wav2LipLipsync, validate_lipsync
from .mux import Muxer, validate_mux
from . import audio, subtitles
from .interfaces import StageStatus


class Orchestrator:
    """Ejecuta el pipeline aplicando la puerta de auditoría antes de avanzar."""

    def __init__(self, workdir: str = "/tmp/voxdub_work"):
        audio.ensure_dir(workdir)
        self.workdir = workdir

    def run_phase1(self, video_path: str, use_mock: bool = True, asr_lang: str = None, cancelled=None):
        wav = f"{self.workdir}/audio.wav"
        audio.extract_audio(video_path, wav)
        tr: Transcriber = MockTranscriber() if use_mock else WhisperTranscriber(language=asr_lang, cancelled=cancelled)
        segments, res = tr.transcribe(wav)
        # Auditoría: no avanzar si no está VERIFIED.
        if res.status != StageStatus.VERIFIED:
            return None, res
        return segments, res

    def run_phase2(self, video_path: str, use_mock: bool = True):
        segments, r1 = self.run_phase1(video_path, use_mock=use_mock)
        if r1.status != StageStatus.VERIFIED:
            return None, r1
        if use_mock:
            det: SpeakerDetector = MockSpeakerDetector()
        else:
            try:
                det = PyannoteDetector()
            except Exception:
                det = MockSpeakerDetector()
        segments, r2 = det.detect(f"{self.workdir}/audio.wav", segments)
        # Auditoría: no avanzar si Detect no está VERIFIED.
        if r2.status != StageStatus.VERIFIED:
            return segments, r2
        return segments, r2

    def run_phase3(self, video_path: str, use_mock: bool = True, target_lang: str = "es",
                   ai_mode: str = "mock", source_lang: str = None):
        segments, r2 = self.run_phase2(video_path, use_mock=use_mock)
        if r2.status != StageStatus.VERIFIED:
            return None, r2
        if ai_mode == "free":
            tr: Translator = FreeTranslator(target_lang, source_lang=source_lang)
        else:
            tr = MockTranslator(target_lang) if use_mock else NLLBTranslator()
        segments, r3 = tr.translate(segments)
        # Auditoría: no avanzar si Translate no está VERIFIED.
        if r3.status != StageStatus.VERIFIED:
            return segments, r3
        return segments, r3

    def run_phase4(self, video_path: str, use_mock: bool = True,
                   target_lang: str = "es", voice_dir: str = "voices",
                   overrides: dict = None):
        segments, r3 = self.run_phase3(video_path, use_mock=use_mock, target_lang=target_lang)
        if r3.status != StageStatus.VERIFIED:
            return None, r3
        syn: Synthesizer = (
            MockSynthesizer(self.workdir, overrides=overrides, voice_dir=voice_dir)
            if use_mock else PiperSynthesizer(self.workdir, voice_dir=voice_dir, overrides=overrides)
        )
        segments, r4 = syn.synthesize(segments)
        # Auditoría: no avanzar si Synthesize no está VERIFIED.
        if r4.status != StageStatus.VERIFIED:
            return segments, r4
        return segments, r4

    def run_phase5(self, video_path: str, use_mock: bool = True,
                   target_lang: str = "es", voice_dir: str = "voices",
                   overrides: dict = None, out_path: str = "/tmp/voxdub_work/out.mp4"):
        # El pipeline completo (incluye lip-sync + mux) vive en run_staged.
        segs, results = self.run_staged(
            video_path, use_mock=use_mock, target_lang=target_lang,
            voice_dir=voice_dir, overrides=overrides, out_path=out_path,
        )
        return segs, results

    def run_staged(self, video_path: str, use_mock: bool = True,
                    target_lang: str = "es", voice_dir: str = "voices",
                    overrides: dict = None, ai_mode: str = "mock",
                    burn_subtitles: bool = False, source_lang: str = None,
                    asr_lang: str = None, cancelled=None,
                    out_path: str = "/tmp/voxdub_work/out.mp4") -> tuple[list, list, dict]:
        """Ejecuta Fase 1..6 guardando el resultado de CADA etapa (auditoría visible).
        `cancelled` es un callable que, si devuelve True, detiene el pipeline entre etapas.
        Devuelve (segmentos, resultados_por_etapa, extras) donde extras incluye subtítulos."""
        results: list = []
        extras: dict = {}
        segs, r = self.run_phase1(video_path, use_mock=use_mock, asr_lang=asr_lang, cancelled=cancelled)
        r.engine = "whisper" if not use_mock else "mock"
        detected = (r.metrics or {}).get("detected_languages") or []
        if detected:
            extras["detected_languages"] = detected
        results.append(("transcribe", r))
        if cancelled and cancelled():
            return segs, results, extras
        if r.status != StageStatus.VERIFIED:
            return segs, results, extras
        segs, r = self.run_phase2(video_path, use_mock=use_mock)
        r.engine = "pyannote" if not use_mock else "mock"
        results.append(("detect", r))
        if cancelled and cancelled():
            return segs, results, extras
        if r.status != StageStatus.VERIFIED:
            return segs, results, extras
        segs, r = self.run_phase3(video_path, use_mock=use_mock, target_lang=target_lang, ai_mode=ai_mode, source_lang=source_lang)
        r.engine = "mymemory" if ai_mode == "free" else ("nllb" if not use_mock else "mock")
        results.append(("translate", r))
        if cancelled and cancelled():
            return segs, results, extras
        if r.status != StageStatus.VERIFIED:
            return segs, results, extras
        # Sintetizar sobre los segmentos YA traducidos (no re-traducir: respeta ai_mode).
        if ai_mode == "free":
            syn: Synthesizer = EdgeTTSSynthesizer(self.workdir, lang=target_lang, overrides=overrides)
        else:
            syn = MockSynthesizer(self.workdir, overrides=overrides, voice_dir=voice_dir) \
                if use_mock else PiperSynthesizer(self.workdir, voice_dir=voice_dir, overrides=overrides)
        segs, r = syn.synthesize(segs)
        r.engine = "edge-tts" if ai_mode == "free" else ("piper" if not use_mock else "mock")
        results.append(("synthesize", r))
        if cancelled and cancelled():
            return segs, results, extras
        if r.status != StageStatus.VERIFIED:
            return segs, results, extras
        # Lip-sync (IA): warpea la boca al audio nuevo. Real = Wav2Lip; si no
        # está configurado, degrada a mock (copia de video) en vez de fallar.
        if use_mock:
            lip = MockLipsync()
            lip_out = os.path.join(os.path.dirname(out_path) or ".", "lipsync.mp4")
            res_lip = lip.sync(video_path, segs, lip_out)
        else:
            lip_out = os.path.join(os.path.dirname(out_path) or ".", "lipsync.mp4")
            try:
                res_lip = Wav2LipLipsync().sync(video_path, segs, lip_out)
            except Exception as e:
                res_lip = MockLipsync().sync(video_path, segs, lip_out)
                res_lip.details = f"Wav2Lip no disponible ({e}); usando mock"
        res_lip.engine = "wav2lip" if not use_mock else "mock"
        results.append(("lipsync", res_lip))
        if cancelled and cancelled():
            return segs, results, extras
        if res_lip.status != StageStatus.VERIFIED:
            return segs, results, extras
        # Mux final: une el audio sintetizado al video con boca sincronizada.
        res = Muxer().mux(res_lip.artifacts.get("video_path", video_path), segs, out_path)
        res.engine = "ffmpeg"
        results.append(("mux", res))
        if cancelled and cancelled():
            return segs, results, extras
        # Subtítulos (paridad con HeyGen/ElevenLabs/Rask): del audio doblado.
        base = os.path.splitext(out_path)[0]
        extras["subtitles"] = subtitles.write_subtitles(segs, base)
        if burn_subtitles and extras["subtitles"].get("srt"):
            try:
                burned = base + ".burned.mp4"
                burn_subtitles(out_path, extras["subtitles"]["srt"], burned, target_lang)
                if os.path.exists(burned):
                    os.replace(burned, out_path)
                    extras["burned"] = True
            except Exception as e:
                extras["burn_error"] = str(e)
        if not any((getattr(s, "text", "") or "").strip() for s in segs):
            extras["warning"] = "No se detectó voz en el video; el resultado no tiene audio doblado."
        return segs, results, extras

    def rerender(self, video_path: str, segments: list, out_path: str,
                 use_mock: bool = True, voice_dir: str = "voices",
                 overrides: dict = None, ai_mode: str = "mock",
                 burn_subtitles: bool = False, cancelled=None, target_lang: str = "es") -> tuple[list, StageResult, dict]:
        """Re-dobla desde los segmentos dados (texto ya corregido) y re-genera subtítulos.
        Usado por el paso de 'revisar y editar traducción'."""
        if not segments:
            return [], StageResult("rerender", StageStatus.FAILED, details="sin segmentos para re-doblar"), {}
        if ai_mode == "free":
            syn: Synthesizer = EdgeTTSSynthesizer(self.workdir, lang=segments[0].lang or "es", overrides=overrides)
        else:
            syn = MockSynthesizer(self.workdir, overrides=overrides, voice_dir=voice_dir) \
                if use_mock else PiperSynthesizer(self.workdir, voice_dir=voice_dir, overrides=overrides)
        segments, r4 = syn.synthesize(segments)
        if cancelled and cancelled():
            return segments, r4, {}
        if r4.status != StageStatus.VERIFIED:
            return segments, r4, {}
        lip_out = os.path.join(os.path.dirname(out_path) or ".", "lipsync_edit.mp4")
        if use_mock:
            res_lip = MockLipsync().sync(video_path, segments, lip_out)
        else:
            try:
                res_lip = Wav2LipLipsync().sync(video_path, segments, lip_out)
            except Exception as e:
                res_lip = MockLipsync().sync(video_path, segments, lip_out)
                res_lip.details = f"Wav2Lip no disponible ({e}); usando mock"
        if res_lip.status != StageStatus.VERIFIED:
            return segments, res_lip, {}
        res = Muxer().mux(res_lip.artifacts.get("video_path", video_path), segments, out_path)
        if res.status != StageStatus.VERIFIED:
            return segments, res, {}
        base = os.path.splitext(out_path)[0]
        extras = {"subtitles": subtitles.write_subtitles(segments, base)}
        if burn_subtitles and extras["subtitles"].get("srt"):
            try:
                burned = base + ".burned.mp4"
                burn_subtitles(out_path, extras["subtitles"]["srt"], burned, target_lang)
                if os.path.exists(burned):
                    os.replace(burned, out_path)
                    extras["burned"] = True
            except Exception as e:
                extras["burn_error"] = str(e)
        return segments, res, extras
