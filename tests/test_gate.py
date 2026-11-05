"""Pocket Gate tests (stdlib unittest, offline, temp runs_dir only)."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))

from app.gate import TWO_KEY_THRESHOLD_USD, GateStore


class TestGateSeeding(unittest.TestCase):
    def test_seeding(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = GateStore(tmp)
            state = store.state()
            self.assertEqual(state["threshold_usd"], 500.0)
            self.assertEqual(TWO_KEY_THRESHOLD_USD, 500.0)
            self.assertIn("two_key_rule", state)
            self.assertTrue(state["two_key_rule"])
            proposals = state["proposals"]
            self.assertEqual(len(proposals), 4)
            self.assertEqual(
                {p["id"] for p in proposals},
                {"sweep-40", "refund-1042", "delist-3", "bump-charizard"},
            )
            for proposal in proposals:
                self.assertEqual(proposal["status"], "pending")
                self.assertIn("title", proposal)
                self.assertIn("detail", proposal)
                self.assertIn("value_usd", proposal)
                self.assertIn("history", proposal)


class TestGateDecisions(unittest.TestCase):
    def test_single_key_approve_under_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = GateStore(tmp)
            updated = store.decide("refund-1042", "approve")
            self.assertEqual(updated["status"], "approved")
            self.assertEqual([h["action"] for h in updated["history"]],
                             ["approve"])

    def test_two_key_flow_for_sweep(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = GateStore(tmp)
            first = store.decide("sweep-40", "approve")
            self.assertEqual(first["status"], "awaiting_second_key")
            second = store.decide("sweep-40", "approve")
            self.assertEqual(second["status"], "approved")
            actions = [h["action"] for h in second["history"]]
            self.assertEqual(actions, ["approve_key_1", "approve_key_2"])

    def test_reject_from_awaiting_second_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = GateStore(tmp)
            store.decide("sweep-40", "approve")
            updated = store.decide("sweep-40", "reject")
            self.assertEqual(updated["status"], "rejected")
            self.assertEqual(updated["history"][-1]["action"], "reject")

    def test_undo_from_approved_returns_to_pending_with_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = GateStore(tmp)
            store.decide("refund-1042", "approve")
            updated = store.decide("refund-1042", "undo")
            self.assertEqual(updated["status"], "pending")
            undo_entries = [h for h in updated["history"]
                            if h["action"] == "undo"]
            self.assertEqual(len(undo_entries), 1)
            self.assertTrue(undo_entries[0].get("token"))

    def test_undo_from_pending_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = GateStore(tmp)
            with self.assertRaises(ValueError):
                store.decide("refund-1042", "undo")

    def test_approve_on_approved_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = GateStore(tmp)
            store.decide("refund-1042", "approve")
            with self.assertRaises(ValueError):
                store.decide("refund-1042", "approve")

    def test_unknown_id_raises_key_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = GateStore(tmp)
            with self.assertRaises(KeyError):
                store.decide("no-such-proposal", "approve")


class TestGatePersistence(unittest.TestCase):
    def test_persistence_across_instances(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = GateStore(tmp)
            store.decide("refund-1042", "approve")
            store.decide("sweep-40", "approve")
            reopened = GateStore(tmp)
            by_id = {p["id"]: p for p in reopened.state()["proposals"]}
            self.assertEqual(by_id["refund-1042"]["status"], "approved")
            self.assertEqual(by_id["sweep-40"]["status"],
                             "awaiting_second_key")
            self.assertEqual(by_id["delist-3"]["status"], "pending")


if __name__ == "__main__":
    unittest.main()
