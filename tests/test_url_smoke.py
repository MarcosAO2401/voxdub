import os
import sys
import threading
import unittest
from http.server import HTTPServer, SimpleHTTPRequestHandler

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "backend"))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from voxdub.fetch_video import download_video  # noqa
from voxdub.jobs import JobManager  # noqa


SAMPLE = "/tmp/voxdub_e2e.mp4"


class _Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/video.mp4":
            with open(SAMPLE, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_response(404)
            self.end_headers()


class TestUrlSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(SAMPLE):
            import subprocess
            subprocess.check_call([
                "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=d=2:s=320x240:r=15",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", SAMPLE,
            ])
        cls.server = HTTPServer(("127.0.0.1", 8137), _Handler)
        t = threading.Thread(target=cls.server.serve_forever, daemon=True)
        t.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_download_and_pipeline(self):
        dest = "/tmp/voxdub_url_test.mp4"
        download_video("http://127.0.0.1:8137/video.mp4", dest)
        self.assertTrue(os.path.exists(dest) and os.path.getsize(dest) > 0)

        jm = JobManager("/tmp/voxdub_url_job")
        job = jm.create(dest, use_mock=True, target_lang="es")
        for _ in range(150):
            if job.status in ("done", "failed"):
                break
            import time
            time.sleep(0.1)
        self.assertEqual(job.status, "done")
        self.assertEqual(len(job.stages), 6)
        self.assertTrue(os.path.exists(job.out_path))


if __name__ == "__main__":
    unittest.main()
