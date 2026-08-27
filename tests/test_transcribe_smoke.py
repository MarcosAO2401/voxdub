import os
import subprocess
import tempfile
import unittest

# make backend importable without install
sys_path = os.path.join(os.path.dirname(__file__), "..", "src", "backend")
import sys
sys.path.insert(0, os.path.abspath(sys_path))

from voxdub.pipeline import MockTranscriber, validate_segments  # noqa
from voxdub.pipeline.interfaces import Segment, StageStatus  # noqa


class TestTranscribeSmoke(unittest.TestCase):
    def _make_wav(self, seconds=2):
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        subprocess.check_call([
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            f"anoisesrc=d={seconds}:c=pink", "-t", str(seconds),
            "-ac", "1", "-ar", "16000", path,
        ])
        return path

    def test_mock_transcribe_passes_audit(self):
        wav = self._make_wav(2)
        segs, res = MockTranscriber().transcribe(wav)
        self.assertEqual(res.status, StageStatus.VERIFIED)
        ok, msg = validate_segments(segs)
        self.assertTrue(ok, msg)
        self.assertTrue(len(segs) >= 1)
        self.assertGreaterEqual(segs[0].end, segs[0].start)

    def test_validate_rejects_negative_duration(self):
        bad = [Segment(1.0, 0.5, "x")]
        ok, msg = validate_segments(bad)
        self.assertFalse(ok)
        self.assertIn("no positiva", msg.lower())

    def test_validate_rejects_empty_text(self):
        bad = [Segment(0.0, 1.0, "   ")]
        ok, msg = validate_segments(bad)
        self.assertFalse(ok)
        self.assertIn("vac", msg.lower())


if __name__ == "__main__":
    unittest.main()
