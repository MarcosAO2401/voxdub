import os
import sys
import subprocess
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "backend")))

from voxdub.pipeline import Muxer, validate_mux  # noqa
from voxdub.pipeline.interfaces import Segment, StageStatus  # noqa


def _make_video(path, seconds=2):
    # Genera un mp4 sintético (video + audio) para probar el mux real.
    subprocess.check_call([
        "ffmpeg", "-y", "-f", "lavfi", "-i", f"testsrc=d={seconds}:s=320x240:r=15",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        path,
    ])


class TestMuxSmoke(unittest.TestCase):
    def test_mux_produces_valid_mp4(self):
        work = "/tmp/voxdub_mux_test"
        os.makedirs(work, exist_ok=True)
        vid = os.path.join(work, "in.mp4")
        _make_video(vid, 2)
        # Dos segmentos de audio silencioso concatenables.
        seg0 = os.path.join(work, "s0.wav")
        seg1 = os.path.join(work, "s1.wav")
        subprocess.check_call(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=d=1",
                               "-t", "1", "-ac", "1", "-ar", "22050", seg0])
        subprocess.check_call(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=d=1",
                               "-t", "1", "-ac", "1", "-ar", "22050", seg1])
        segs = [
            Segment(0.0, 1.0, "a", audio_path=seg0),
            Segment(1.0, 2.0, "b", audio_path=seg1),
        ]
        out = os.path.join(work, "out.mp4")
        res = Muxer().mux(vid, segs, out)
        self.assertEqual(res.status, StageStatus.VERIFIED)
        ok, msg = validate_mux(out)
        self.assertTrue(ok, msg)
        self.assertTrue(os.path.getsize(out) > 0)

    def test_validate_mux_rejects_missing_file(self):
        ok, msg = validate_mux("/no/existe.mp4")
        self.assertFalse(ok)
        self.assertIn("creado", msg.lower())


if __name__ == "__main__":
    unittest.main()
