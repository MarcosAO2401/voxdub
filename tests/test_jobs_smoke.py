import os
import sys
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "backend")))

from voxdub.jobs import JobManager  # noqa


def _make_video(path, seconds=2):
    import subprocess
    subprocess.check_call([
        "ffmpeg", "-y", "-f", "lavfi", "-i", f"testsrc=d={seconds}:s=320x240:r=15",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", path,
    ])


class TestJobManagerSmoke(unittest.TestCase):
    def test_job_runs_stages_and_completes(self):
        work = "/tmp/voxdub_job_test"
        os.makedirs(work, exist_ok=True)
        vid = os.path.join(work, "in.mp4")
        _make_video(vid, 2)
        jm = JobManager(work)
        job = jm.create(vid, use_mock=True)
        # esperar a que termine (mock es rápido, pero damos margen bajo carga)
        for _ in range(150):
            if job.status in ("done", "failed"):
                break
            time.sleep(0.1)
        self.assertEqual(job.status, "done")
        self.assertEqual(len(job.stages), 6)
        names = [s["name"] for s in job.stages]
        self.assertEqual(names, ["transcribe", "detect", "translate", "synthesize", "lipsync", "mux"])
        for s in job.stages:
            self.assertEqual(s["status"], "verified")
        self.assertTrue(os.path.exists(job.out_path))

    def test_job_fails_safe_on_bad_input(self):
        jm = JobManager("/tmp/voxdub_job_test2")
        job = jm.create("/ruta/inexistente.mp4", use_mock=True)
        for _ in range(150):
            if job.status in ("done", "failed"):
                break
            time.sleep(0.1)
        self.assertEqual(job.status, "failed")
        self.assertIsNotNone(job.error)


if __name__ == "__main__":
    unittest.main()
