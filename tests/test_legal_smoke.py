import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "backend"))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from voxdub.api import legal  # noqa


class TestLegalSmoke(unittest.TestCase):
    def test_legal_endpoint(self):
        terms = legal()
        self.assertIn("title", terms)
        self.assertIn("responsible_use", terms)
        self.assertIn("rules", terms)
        self.assertIsInstance(terms["rules"], list)
        self.assertTrue(len(terms["rules"]) >= 3)
        self.assertIn("disclaimer", terms)


if __name__ == "__main__":
    unittest.main()
