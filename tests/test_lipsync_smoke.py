import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "backend")))

from voxdub.pipeline import MockLipsync, validate_lipsync  # noqa
from voxdub.pipeline.interfaces import Segment, StageStatus  # noqa


class TestLipsyncSmoke(unittest.TestCase):
    def test_mock_lipsync_produces_video(self):
        work = "/tmp/voxdub_lip_test"
        os.makedirs(work, exist_ok=True)
        # video sintético
        vid = os.path.join(work, "in.mp4")
        import subprocess
        subprocess.check_call([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=d=1:s=320x240:r=15",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", vid,
        ])
        segs = [Segment(0.0, 1.0, "a", audio_path=vid)]
        out = os.path.join(work, "lip.mp4")
        res = MockLipsync().sync(vid, segs, out)
        self.assertEqual(res.status, StageStatus.VERIFIED)
        ok, msg = validate_lipsync(out)
        self.assertTrue(ok, msg)
        self.assertTrue(os.path.getsize(out) > 0)

    def test_validate_lipsync_rejects_missing(self):
        ok, msg = validate_lipsync("/no/existe.mp4")
        self.assertFalse(ok)
        self.assertIn("creado", msg.lower())


if __name__ == "__main__":
    unittest.main()
