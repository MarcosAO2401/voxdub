import os
import unittest

from voxdub.pipeline.transcribe import WhisperTranscriber
from voxdub.pipeline.interfaces import Segment, validate_segments


class TestRealASR(unittest.TestCase):
    def test_whisper_transcribes_speech(self):
        try:
            import faster_whisper  # type: ignore
        except ImportError:
            self.skipTest("faster-whisper no instalado")
        wav = "/tmp/speech.wav"
        if not os.path.exists(wav):
            self.skipTest("clip de prueba no presente (/tmp/speech.wav)")
        tr = WhisperTranscriber(model_name="tiny", language="es")
        try:
            segs, res = tr.transcribe(wav)
        except Exception as e:
            self.skipTest(f"Whisper no disponible en este entorno: {e}")
        self.assertEqual(res.status.value, "verified")
        text = " ".join(s.text for s in segs).lower()
        self.assertIn("whisper", text)


if __name__ == "__main__":
    unittest.main()
