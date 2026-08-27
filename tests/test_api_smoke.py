import os
import sys
import threading
import time
import unittest
from http.server import HTTPServer, SimpleHTTPRequestHandler

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "backend"))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fastapi.testclient import TestClient  # noqa
from voxdub.api import app  # noqa

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


class TestApiSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(SAMPLE):
            import subprocess
            subprocess.check_call([
                "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=d=2:s=320x240:r=15",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", SAMPLE,
            ])
        cls.server = HTTPServer(("127.0.0.1", 8139), _Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_create_by_url_no_body(self):
        r = self.client.post("/jobs", params={"mock": True, "url": "http://127.0.0.1:8139/video.mp4"})
        self.assertEqual(r.status_code, 200, r.text)
        jid = r.json()["job_id"]
        for _ in range(150):
            job = self.client.get(f"/jobs/{jid}").json()
            if job["status"] in ("done", "failed"):
                break
            time.sleep(0.1)
        self.assertEqual(job["status"], "done")
        self.assertEqual(len(job["stages"]), 6)

    def test_invalid_url_rejected(self):
        r = self.client.post("/jobs", params={"mock": True, "url": "http://127.0.0.1:8139/nope.mp4"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("detail", r.json())


if __name__ == "__main__":
    unittest.main()
