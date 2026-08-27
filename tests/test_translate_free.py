import unittest
from unittest.mock import patch
from voxdub.pipeline.translate import FreeTranslator, MockTranslator
from voxdub.pipeline.interfaces import Segment


class FakeResp:
    def __init__(self, payload):
        self._p = payload.encode()

    def read(self):
        return self._p

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class TestFreeTranslator(unittest.TestCase):
    def test_free_translator_parses_mymemory(self):
        body = '{"responseData":{"translatedText":"hola mundo"},"responseStatus":200}'
        with patch("voxdub.pipeline.translate.urllib.request.urlopen", return_value=FakeResp(body)):
            tr = FreeTranslator(target_lang="es")
            segs = [Segment(0.0, 1.0, "hello world")]
            out, res = tr.translate(segs)
        self.assertEqual(out[0].source_text, "hello world")
        self.assertEqual(out[0].text, "hola mundo")
        self.assertEqual(res.status.value, "verified")

    def test_free_translator_failure_marks_failed(self):
        with patch("voxdub.pipeline.translate.urllib.request.urlopen", side_effect=RuntimeError("net")):
            tr = FreeTranslator(target_lang="es")
            segs = [Segment(0.0, 1.0, "hello")]
            out, res = tr.translate(segs)
        self.assertEqual(res.status.value, "failed")

    def test_mock_translator_still_works(self):
        tr = MockTranslator("es")
        segs = [Segment(0.0, 1.0, "hello")]
        out, res = tr.translate(segs)
        self.assertEqual(res.status.value, "verified")
        self.assertTrue(out[0].text)


if __name__ == "__main__":
    unittest.main()
