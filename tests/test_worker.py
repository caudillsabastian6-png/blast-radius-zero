"""Tests for the sandbox worker via the LOCAL backend.

The local backend is a development convenience (process separation + scrubbed
environment + temp workspace), not the security boundary - these tests verify
executor behaviour that both backends share: the JSON-lines protocol, the
workspace path jail, timeouts, output shape, and the environment whitelist.
Docker-only guarantees (no network, no host FS) are tested in test_loop.py
and skip when Docker is unavailable.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))

from app.sandbox_client import LocalSandboxSession


class TestLocalWorker(unittest.TestCase):
    def setUp(self):
        self.session = LocalSandboxSession()

    def tearDown(self):
        self.session.close()

    def test_write_read_roundtrip(self):
        resp = self.session.execute("write_file", {"path": "docs/a.txt", "content": "hello sandbox"})
        self.assertTrue(resp["ok"], resp)
        resp = self.session.execute("read_file", {"path": "docs/a.txt"})
        self.assertTrue(resp["ok"], resp)
        self.assertEqual(resp["result"]["content"], "hello sandbox")

    def test_list_files(self):
        self.session.execute("write_file", {"path": "x.csv", "content": "a,b\n1,2\n"})
        resp = self.session.execute("list_files", {"path": "."})
        self.assertTrue(resp["ok"], resp)
        paths = [e["path"] for e in resp["result"]["entries"]]
        self.assertIn("x.csv", paths)

    def test_run_shell(self):
        resp = self.session.execute("run_shell", {"cmd": "echo brz-ok && pwd"})
        self.assertTrue(resp["ok"], resp)
        self.assertEqual(resp["result"]["exit_code"], 0)
        self.assertIn("brz-ok", resp["result"]["stdout"])
        self.assertIn(self.session.workspace, resp["result"]["stdout"])

    def test_run_shell_timeout(self):
        resp = self.session.execute("run_shell", {"cmd": "sleep 5", "timeout": 1})
        self.assertTrue(resp["ok"], resp)
        self.assertTrue(resp["result"]["timed_out"])

    def test_jail_blocks_dotdot_escape(self):
        resp = self.session.execute("write_file", {"path": "../escape.txt", "content": "x"})
        self.assertFalse(resp["ok"])
        self.assertIn("JailError", resp["error"])

    def test_jail_blocks_absolute_path(self):
        resp = self.session.execute("read_file", {"path": "/etc/passwd"})
        self.assertFalse(resp["ok"])
        self.assertIn("JailError", resp["error"])

    def test_environment_is_scrubbed(self):
        os.environ["BRZ_LEAK_TEST_SECRET"] = "should-not-reach-the-worker"
        try:
            session = LocalSandboxSession()
            try:
                resp = session.execute("probe")
                self.assertTrue(resp["ok"], resp)
                self.assertNotIn("BRZ_LEAK_TEST_SECRET", resp["result"]["env_var_names"])
                self.assertEqual(resp["result"]["secret_like_env_vars"], [])
                resp = session.execute("run_shell", {"cmd": "printenv"})
                self.assertNotIn("should-not-reach-the-worker", resp["result"]["stdout"])
            finally:
                session.close()
        finally:
            del os.environ["BRZ_LEAK_TEST_SECRET"]

    def test_probe_shape(self):
        resp = self.session.execute("probe")
        self.assertTrue(resp["ok"], resp)
        result = resp["result"]
        for key in ("env_var_names", "secret_like_env_vars", "docker_socket_present",
                    "network_test", "workspace"):
            self.assertIn(key, result)
        self.assertIn("reachable", result["network_test"])

    def test_unknown_op(self):
        resp = self.session.execute("nuke_everything")
        self.assertFalse(resp["ok"])


if __name__ == "__main__":
    unittest.main()
