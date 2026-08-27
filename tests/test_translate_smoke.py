import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "backend")))

from voxdub.pipeline import MockTranslator, validate_translation  # noqa
from voxdub.pipeline.interfaces import Segment, StageStatus  # noqa


class TestTranslateSmoke(unittest.TestCase):
    def _segs(self, n=3):
        return [Segment(round(i, 3), round(i + 1, 3), f"hello {i}") for i in range(n)]

    def test_mock_translates_and_sets_lang(self):
        segs, res = MockTranslator(target_lang="es").translate(self._segs(3))
        self.assertEqual(res.status, StageStatus.VERIFIED)
        ok, msg = validate_translation(segs)
        self.assertTrue(ok, msg)
        for s in segs:
            self.assertEqual(s.lang, "es")
            self.assertIn("traducido", s.text)

    def test_validate_allows_empty_text_as_silence(self):
        # Un segmento vacío representa silencio (video sin voz) y se permite.
        silent = [Segment(0.0, 1.0, "   ", lang="es")]
        ok, msg = validate_translation(silent)
        self.assertTrue(ok)

    def test_validate_rejects_missing_lang_on_real_text(self):
        # Un segmento con texto real pero sin idioma destino sí se rechaza.
        bad = [Segment(0.0, 1.0, "hola")]
        ok, msg = validate_translation(bad)
        self.assertFalse(ok)
        self.assertIn("idioma", msg.lower())

    def test_validate_rejects_missing_lang(self):
        bad = [Segment(0.0, 1.0, "hola")]
        ok, msg = validate_translation(bad)
        self.assertFalse(ok)
        self.assertIn("idioma", msg.lower())


if __name__ == "__main__":
    unittest.main()
