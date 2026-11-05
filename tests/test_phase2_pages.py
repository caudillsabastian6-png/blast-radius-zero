"""Phase-2 board page tests: Night Shift + Rewind pages carry the
honesty labels and wire to their status endpoints.

Offline and stdlib-only, like the rest of the suite.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))

from app.nightshift_page import page as nightshift_page
from app.rewind_page import page as rewind_page


class TestNightShiftPage(unittest.TestCase):
    def test_labels_and_endpoints(self):
        html = nightshift_page()
        self.assertIn("Night Shift", html)
        self.assertIn("/nightshift/status", html)
        self.assertIn("/nightshift/run", html)
        self.assertIn("simulated on demo data", html)
        self.assertIn("Pocket Gate", html)
        self.assertIn("Nothing applies overnight", html)


class TestRewindPage(unittest.TestCase):
    def test_labels_and_endpoints(self):
        html = rewind_page()
        self.assertIn("Rewind", html)
        self.assertIn("/rewind/status", html)
        self.assertIn("/rewind/run", html)
        self.assertIn("simulated on demo data", html)
        self.assertIn("Died in rehearsal", html)
        self.assertIn("Expected-safe", html)
        self.assertIn("never", html)


if __name__ == "__main__":
    unittest.main()
