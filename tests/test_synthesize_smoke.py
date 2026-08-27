import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "backend")))

from voxdub.pipeline import MockSynthesizer, validate_synthesis  # noqa
from voxdub.pipeline.interfaces import Segment, StageStatus  # noqa


class TestSynthesizeSmoke(unittest.TestCase):
    def _segs(self):
        return [
            Segment(0.0, 1.0, "hola", speaker="spk0", gender="female", lang="es"),
            Segment(1.0, 2.0, "mundo", speaker="spk1", gender="male", lang="es"),
        ]

    def test_mock_writes_audio_artifacts(self):
        work = "/tmp/voxdub_syn_test"
        segs, res = MockSynthesizer(work).synthesize(self._segs())
        self.assertEqual(res.status, StageStatus.VERIFIED)
        ok, msg = validate_synthesis(segs)
        self.assertTrue(ok, msg)
        for s in segs:
            self.assertIsNotNone(s.audio_path)
            self.assertTrue(os.path.getsize(s.audio_path) > 0)

    def test_validate_rejects_missing_audio(self):
        bad = [Segment(0.0, 1.0, "x", audio_path="/no/existe.wav")]
        ok, msg = validate_synthesis(bad)
        self.assertFalse(ok)
        self.assertIn("audio", msg.lower())


if __name__ == "__main__":
    unittest.main()
