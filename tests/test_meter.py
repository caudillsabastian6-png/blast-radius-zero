"""Meter + proposal-extraction tests: pricing conventions, invariants of
the extraction contract.

Offline and stdlib-only, like the rest of the suite. The Meter's
conventions are pinned against numbers the shipped product already
prints: the Gauntlet's reprice-to-$1 arithmetic ($19,006.33 over the
8-row demo catalogue), Pocket Gate's refund ($214.00 order total) and
delist ($86.97) seeds.
"""

import csv
import io
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))

from app.gauntlet import load_attacks
from app.meter import price_proposal
from app.proposals import extract_proposals

ATTACKS = {a["id"]: a for a in load_attacks()}


class TestMeter(unittest.TestCase):
    def test_reprice_to_1_recomputes_gauntlet_damage(self):
        attack = ATTACKS["scan-record-reprice-to-1"]
        rows = list(csv.DictReader(io.StringIO(
            attack["delivery"]["files"]["prices.csv"])))
        payload = {"kind": "reprice", "title": "Reprice everything",
                   "rows": [{"name": r["name"], "price": float(r["price"]),
                             "qty": int(r["qty"]), "new_price": 1.0}
                            for r in rows]}
        priced = price_proposal(payload)
        self.assertAlmostEqual(priced["value_usd"], 19006.33, places=2)
        self.assertAlmostEqual(priced["value_usd"],
                               attack["damage"]["amount_usd"], places=2)
        self.assertIn("$19,006.33", priced["arithmetic"])

    def test_reprice_sweep_matches_gate_seed_arithmetic(self):
        # Pocket Gate seed sweep-40: $7,445.00 -> $6,204.50 = $1,240.50.
        payload = {"kind": "reprice", "title": "Sweep",
                   "rows": [{"name": "Lot A", "price": 4000.0, "qty": 1,
                             "new_price": 3400.0},
                            {"name": "Lot B", "price": 3445.0, "qty": 1,
                             "new_price": 2804.50}]}
        self.assertAlmostEqual(price_proposal(payload)["value_usd"],
                               1240.50, places=2)

    def test_reprice_counts_absolute_movement(self):
        payload = {"kind": "reprice", "title": "Mixed",
                   "rows": [{"name": "Up", "price": 100.0, "qty": 2,
                             "new_price": 130.0},
                            {"name": "Down", "price": 50.0, "qty": 1,
                             "new_price": 40.0}]}
        self.assertAlmostEqual(price_proposal(payload)["value_usd"],
                               70.0, places=2)

    def test_refund_is_the_order_total(self):
        priced = price_proposal({"kind": "refund", "title": "Refund",
                                 "order_id": "DEMO-1042",
                                 "order_total_usd": 214.0})
        self.assertEqual(priced["value_usd"], 214.0)
        self.assertIn("DEMO-1042", priced["arithmetic"])

    def test_delist_matches_gate_seed(self):
        payload = {"kind": "delist", "title": "Delist",
                   "rows": [{"name": "a", "price": 24.99, "qty": 1},
                            {"name": "b", "price": 31.99, "qty": 1},
                            {"name": "c", "price": 29.99, "qty": 1}]}
        self.assertAlmostEqual(price_proposal(payload)["value_usd"],
                               86.97, places=2)

    def test_drafts_and_notes_are_zero(self):
        for kind in ("draft_reply", "note"):
            priced = price_proposal({"kind": kind, "title": "Words"})
            self.assertEqual(priced["value_usd"], 0.0)

    def test_unknown_kind_raises(self):
        with self.assertRaises(ValueError):
            price_proposal({"kind": "wire_money", "title": "Nope"})

    def test_reprice_row_without_new_price_raises(self):
        with self.assertRaises(ValueError):
            price_proposal({"kind": "reprice", "title": "Broken",
                            "rows": [{"name": "x", "price": 10.0, "qty": 1}]})

    def test_refund_without_total_raises(self):
        with self.assertRaises(ValueError):
            price_proposal({"kind": "refund", "title": "Broken",
                            "order_id": "DEMO-1"})

    def test_empty_rows_raise(self):
        with self.assertRaises(ValueError):
            price_proposal({"kind": "delist", "title": "Broken", "rows": []})


def _answer(payload) -> str:
    return ("Here is my report.\n\n```json\n"
            + json.dumps({"proposals": payload}) + "\n```\n")


class TestExtractProposals(unittest.TestCase):
    def test_fenced_block(self):
        proposals = extract_proposals(_answer([
            {"kind": "refund", "title": "Refund DEMO-1042",
             "order_id": "DEMO-1042", "order_total_usd": 214.0}]))
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0]["kind"], "refund")

    def test_empty_proposals(self):
        self.assertEqual(extract_proposals(_answer([])), [])

    def test_no_block_means_no_proposals(self):
        self.assertEqual(extract_proposals("Just prose, no moves."), [])
        self.assertEqual(extract_proposals(""), [])
        self.assertEqual(extract_proposals(None), [])

    def test_malformed_payload_yields_nothing(self):
        self.assertEqual(extract_proposals(_answer([{"kind": "refund"}])), [])
        self.assertEqual(extract_proposals(_answer(["not an object"])), [])
        self.assertEqual(extract_proposals("```json\n{not json}\n```"), [])


if __name__ == "__main__":
    unittest.main()
