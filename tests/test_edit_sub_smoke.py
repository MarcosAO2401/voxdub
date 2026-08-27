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


class TestEditSubtitlesSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(SAMPLE):
            import subprocess
            subprocess.check_call([
                "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=d=2:s=320x240:r=15",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", SAMPLE,
            ])
        cls.server = HTTPServer(("127.0.0.1", 8140), _Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def _wait(self, jid, timeout=60):
        for _ in range(timeout * 10):
            job = self.client.get(f"/jobs/{jid}").json()
            if job["status"] in ("done", "failed"):
                return job
            time.sleep(0.1)
        return self.client.get(f"/jobs/{jid}").json()

    def test_transcript_edit_and_subtitles(self):
        r = self.client.post("/jobs", params={"mock": True, "url": "http://127.0.0.1:8140/video.mp4"})
        self.assertEqual(r.status_code, 200)
        jid = r.json()["job_id"]
        job = self._wait(jid)
        self.assertEqual(job["status"], "done")

        # Transcripción
        tr = self.client.get(f"/jobs/{jid}/transcript").json()
        self.assertIn("segments", tr)
        self.assertTrue(len(tr["segments"]) > 0)
        seg = tr["segments"][0]
        self.assertIn("source", seg)
        self.assertIn("target", seg)

        # Subtítulos
        srt = self.client.get(f"/jobs/{jid}/subtitles", params={"fmt": "srt"})
        self.assertEqual(srt.status_code, 200)
        self.assertIn("-->", srt.text)

        # Editar y regenerar
        new_text = "TEXTO EDITADO PARA AUDITORIA"
        r2 = self.client.post(f"/jobs/{jid}/apply_translation",
                              json={"overrides": {str(seg["index"]): new_text}})
        self.assertEqual(r2.status_code, 200)
        job2 = self._wait(jid)
        self.assertEqual(job2["status"], "done")

        tr2 = self.client.get(f"/jobs/{jid}/transcript").json()
        edited = [s for s in tr2["segments"] if s["index"] == seg["index"]][0]
        self.assertIn(new_text, edited["target"])


if __name__ == "__main__":
    unittest.main()
