import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "backend")))

from voxdub.pipeline import MockSpeakerDetector, validate_detection, assign_default_voices  # noqa
from voxdub.pipeline.interfaces import Segment, StageStatus  # noqa
from voxdub.pipeline.synthesize import DEFAULT_VOICES  # noqa


class TestDetectSmoke(unittest.TestCase):
    def _segs(self, n=4):
        return [Segment(round(i * 1.0, 3), round((i + 1) * 1.0, 3), f"texto {i}") for i in range(n)]

    def test_mock_assigns_speaker_and_gender(self):
        segs, res = MockSpeakerDetector(n_speakers=2).detect("x.wav", self._segs(4))
        self.assertEqual(res.status, StageStatus.VERIFIED)
        ok, msg = validate_detection(segs)
        self.assertTrue(ok, msg)
        genders = {s.gender for s in segs}
        self.assertTrue(genders.issubset({"male", "female", "unknown"}))
        speakers = {s.speaker for s in segs}
        self.assertEqual(len(speakers), 2)

    def test_assign_default_voices(self):
        segs, _ = MockSpeakerDetector(n_speakers=2).detect("x.wav", self._segs(4))
        mapping = assign_default_voices(segs)
        for spk, voice in mapping.items():
            self.assertIn(voice, DEFAULT_VOICES.values())

    def test_override_voice(self):
        segs, _ = MockSpeakerDetector(n_speakers=1).detect("x.wav", self._segs(2))
        mapping = assign_default_voices(segs, overrides={"spk0": "voz-personalizada"})
        self.assertEqual(mapping["spk0"], "voz-personalizada")

    def test_validate_detection_rejects_missing_speaker(self):
        bad = [Segment(0.0, 1.0, "x")]  # sin speaker
        ok, msg = validate_detection(bad)
        self.assertFalse(ok)
        self.assertIn("hablante", msg.lower())


if __name__ == "__main__":
    unittest.main()
