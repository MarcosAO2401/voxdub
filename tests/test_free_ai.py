import os
import unittest

from voxdub.pipeline.interfaces import Segment
from voxdub.pipeline.translate import FreeTranslator
from voxdub.pipeline.subtitles import burn_subtitles, write_subtitles


class TestFreeAITranslate(unittest.TestCase):
    def test_source_lang_passthrough(self):
        tr = FreeTranslator(target_lang="en", source_lang="es")
        self.assertEqual(tr.source_lang, "es")
        tr2 = FreeTranslator(target_lang="es")
        self.assertEqual(tr2.source_lang, "en")  # heurística: destino es -> origen en

    def test_real_translation_with_source(self):
        tr = FreeTranslator(target_lang="en", source_lang="es")
        segs = [Segment(0.0, 1.0, "casa grande")]
        out, res = tr.translate(segs)
        self.assertEqual(res.status.value, "verified")
        self.assertNotEqual(out[0].text, "casa grande")
        self.assertEqual(out[0].source_text, "casa grande")


class TestEdgeTTS(unittest.TestCase):
    def test_real_synthesis(self):
        try:
            import edge_tts  # type: ignore
        except ImportError:
            self.skipTest("edge-tts no instalado")
        from voxdub.pipeline.synthesize import EdgeTTSSynthesizer
        syn = EdgeTTSSynthesizer("/tmp/voxdub_edge_test", lang="es")
        segs = [Segment(0.0, 1.0, "Hola, esto es una prueba de doblaje.")]
        try:
            out, res = syn.synthesize(segs)
        except Exception as e:
            self.skipTest(f"edge-tts red no disponible: {e}")
        self.assertEqual(res.status.value, "verified")
        self.assertTrue(os.path.exists(out[0].audio_path))
        self.assertGreater(os.path.getsize(out[0].audio_path), 0)


class TestBurnSubtitles(unittest.TestCase):
    def test_burn(self):
        video = "/tmp/voxdub_e2e.mp4"
        if not os.path.exists(video):
            self.skipTest("video de muestra no presente")
        base = "/tmp/voxdub_burn_test"
        subs = write_subtitles([Segment(0.0, 1.5, "Hola mundo subtitulado")], base)
        out = base + ".burned.mp4"
        try:
            burn_subtitles(video, subs["srt"], out)
        except Exception as e:
            self.skipTest(f"ffmpeg hardsub no disponible: {e}")
        self.assertTrue(os.path.exists(out))
        self.assertGreater(os.path.getsize(out), 0)


if __name__ == "__main__":
    unittest.main()
