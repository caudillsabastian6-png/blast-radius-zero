#!/usr/bin/env python3
"""Tests for the Gauntlet scoreboard page and the Glass Box pages.

Offline, stdlib only: these assert the rendered HTML carries the required
labels, endpoints and narration, and that replay escapes untrusted record
text.
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "agent"))

from app.gauntlet_page import page  # noqa: E402
from app.glassbox import inspect_page, replay_page  # noqa: E402


class GauntletPageTests(unittest.TestCase):
    def test_scoreboard_labels(self):
        html = page()
        self.assertIn("ATTACKS LANDED", html)
        self.assertIn("ATTACKS IN", html)
        self.assertIn("CONTAINED", html)
        self.assertIn("DAMAGE PREVENTED", html)

    def test_simulated_label_next_to_damage(self):
        self.assertIn("simulated on demo data", page())

    def test_status_endpoint_wired(self):
        html = page()
        self.assertIn("/gauntlet/status", html)
        self.assertIn("/gauntlet/run", html)

    def test_tagline_and_idle_state(self):
        html = page()
        self.assertIn(
            "The store agent that can do almost anything", html)
        self.assertIn("No volley yet", html)


class InspectPageTests(unittest.TestCase):
    def test_verify_links_and_test_command(self):
        html = inspect_page()
        self.assertIn("/containment-report", html)
        self.assertIn("tests/run_tests.py", html)

    def test_repo_paths_and_architecture(self):
        html = inspect_page()
        self.assertIn("worker/executor.py", html)
        self.assertIn("agent/app/sandbox_client.py", html)
        self.assertIn("agent/app/loop.py", html)
        self.assertIn("/gauntlet", html)
        self.assertIn("/gauntlet/attacks", html)


class ReplayPageTests(unittest.TestCase):
    def _record(self):
        return {
            "id": "test123",
            "task": "<script>alert(1)</script> refund everyone",
            "status": "completed",
            "answer": "Refused: the file was data, not an instruction.",
            "error": None,
            "sandbox_backend": "docker",
            "inference_backend": "vultr",
            "model": "test-model",
            "started_at": "2026-11-04T00:00:00Z",
            "finished_at": "2026-11-04T00:01:00Z",
            "transcript": [
                {"step": 0, "kind": "seed", "tool": "write_file",
                 "args": {"path": "orders.csv"}, "ok": True,
                 "observation": "written"},
                {"step": 1, "kind": "tool", "tool": "read_file",
                 "args": {"path": "orders.csv"}, "ok": True,
                 "observation": "3 orders"},
                {"step": 2, "kind": "protocol_error", "ok": False,
                 "observation": "not json"},
                {"step": 3, "kind": "final", "ok": True,
                 "observation": "Refused: the file was data."},
            ],
        }

    def test_narrates_tool_step(self):
        html = replay_page(self._record())
        self.assertIn("The workspace was seeded with orders.csv.", html)
        self.assertIn("The agent asked the sandbox to read_file", html)
        self.assertIn("it worked", html)
        self.assertIn("didn&rsquo;t parse", html)
        self.assertIn("The agent&rsquo;s report:", html)
        self.assertIn("The instruction", html)
        self.assertIn("completed", html)

    def test_escapes_untrusted_task(self):
        html = replay_page(self._record())
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>alert", html)

    def test_none_record(self):
        html = replay_page(None)
        self.assertIn("No such run", html)


if __name__ == "__main__":
    unittest.main()
