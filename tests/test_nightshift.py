"""Night Shift tests: fixture schema, budget enforcement, handoffs,
gate delivery.

Offline and stdlib-only, like the rest of the suite. The shift test uses
a stub agent_loop returning canned records in call order, so no
inference, no sandbox and no Docker are involved. The designed night is
the fixture's own arithmetic: Pricer forwards $500.00 + $644.60 +
$350.00 = $1,494.60 of its $1,500 budget and its $400.00 Venusaur
proposal is cut; Watcher's $260.00 refund is cut even though Pricer
still has headroom (budgets do not transfer).
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))

from app import nightshift
from app.config import Config
from app.gate import GateStore
from app.glassbox import replay_page
from app.nightshift import NightShiftRunner, SPECIALISTS, load_night

NIGHT = load_night()


def _record(answer=None, transcript=None, run_id="run-x", status="completed"):
    return {"id": run_id, "status": status, "answer": answer,
            "transcript": transcript or [], "sandbox_backend": "local"}


def _answer(*proposals) -> str:
    return ("Report follows.\n\n```json\n"
            + json.dumps({"proposals": list(proposals)}) + "\n```\n")


class _FakeLoop:
    """Stub AgentLoop: returns canned records in call order, records calls."""

    def __init__(self, records):
        self._records = list(records)
        self.calls = []

    def run(self, task, seed_files=None):
        self.calls.append({"task": task, "seed_files": seed_files})
        return self._records.pop(0)


def _shift_records():
    """One canned record per run of the designed night, in order."""
    watcher_first = _record(
        answer="Reviewed the orders. One anomaly: Charizard is priced "
               "well under its recent sold price; flagging for Pricer.",
        transcript=[{"step": 1, "kind": "tool", "tool": "run_shell",
                     "args": {"cmd": "ls"}, "ok": True, "observation": "{}"}],
        run_id="run-watch-1")
    handoff = _record(answer=_answer(
        {"kind": "reprice", "title": "Reprice Charizard to sold price",
         "detail": "Charizard is listed $50 under its recent sold price.",
         "rows": [{"name": "Charizard Base Set Holo", "price": 499.99,
                   "qty": 10, "new_price": 549.99}]}), run_id="run-handoff")
    sweep = _record(answer=_answer(
        {"kind": "reprice", "title": "Market sweep: four listings",
         "detail": "Four listings drifted from tonight's sold prices.",
         "rows": [
             {"name": "Pikachu Yellow Cheeks", "price": 24.50, "qty": 40,
              "new_price": 29.99},
             {"name": "Blastoise Base Set Holo", "price": 349.99, "qty": 6,
              "new_price": 329.99},
             {"name": "Gengar Fossil Holo", "price": 129.99, "qty": 18,
              "new_price": 139.99},
             {"name": "Mewtwo Base Set Holo", "price": 59.99, "qty": 25,
              "new_price": 64.99}]}), run_id="run-sweep")
    inbox = _record(answer=_answer(
        {"kind": "draft_reply", "title": "Draft reply: tracking question",
         "detail": "Reassure the DEMO-2071 buyer; tracking attached."},
        {"kind": "draft_reply", "title": "Draft reply: combined shipping",
         "detail": "Agree to combine shipping with the Gengar order."}),
        run_id="run-inbox")
    scan = _record(answer=_answer(
        {"kind": "refund", "title": "Refund DEMO-1042 (not as described)",
         "detail": "Confirmed not-as-described return; refund the total.",
         "order_id": "DEMO-1042", "order_total_usd": 214.0}),
        run_id="run-scan")
    stale = _record(answer=_answer(
        {"kind": "delist", "title": "Delist three stale listings",
         "detail": "No views in 90 days; duplicates of newer listings.",
         "rows": [{"name": "Base Set Energy (stale duplicate)",
                   "price": 24.99, "qty": 1},
                  {"name": "Fossil Common (stale duplicate)",
                   "price": 31.99, "qty": 1},
                  {"name": "Jungle Common (stale duplicate)",
                   "price": 29.99, "qty": 1}]}), run_id="run-stale")
    corrections = _record(answer=_answer(
        {"kind": "reprice", "title": "Gold-star corrections",
         "detail": "Umbreon and Lugia both drifted up overnight.",
         "rows": [{"name": "Umbreon Gold Star", "price": 899.99, "qty": 3,
                   "new_price": 949.99},
                  {"name": "Lugia Neo Genesis Holo", "price": 749.50,
                   "qty": 4, "new_price": 799.50}]},
        {"kind": "reprice", "title": "Venusaur correction",
         "detail": "Venusaur drifted up overnight.",
         "rows": [{"name": "Venusaur Base Set Holo", "price": 299.99,
                   "qty": 5, "new_price": 379.99}]}),
        run_id="run-corrections")
    claim = _record(answer=_answer(
        {"kind": "refund", "title": "Refund DEMO-2077 (claimed non-delivery)",
         "detail": "Buyer claims non-delivery; tracking unchecked.",
         "order_id": "DEMO-2077", "order_total_usd": 260.0}),
        run_id="run-claim")
    last_inbox = _record(answer=_answer(
        {"kind": "draft_reply", "title": "Draft reply: loyalty code request",
         "detail": "Politely decline; codes are the owner's to give."}),
        run_id="run-inbox-2")
    return [watcher_first, handoff, sweep, inbox, scan, stale,
            corrections, claim, last_inbox]


class TestNightFixture(unittest.TestCase):
    def test_eight_events_unique_ids_known_specialists(self):
        events = NIGHT["events"]
        self.assertEqual(len(events), 8)
        self.assertEqual(len({e["id"] for e in events}), 8)
        for event in events:
            self.assertIn(event["specialist"], SPECIALISTS)

    def test_exactly_one_handoff_with_a_reason(self):
        handoffs = [e["handoff"] for e in NIGHT["events"] if e.get("handoff")]
        self.assertEqual(len(handoffs), 1)
        self.assertEqual(handoffs[0]["to"], "pricer")
        self.assertIn("Charizard", handoffs[0]["reason"])

    def test_budgets(self):
        self.assertEqual(SPECIALISTS["pricer"]["budget_usd"], 1500.0)
        self.assertEqual(SPECIALISTS["watcher"]["budget_usd"], 300.0)
        self.assertEqual(SPECIALISTS["greeter"]["budget_usd"], 250.0)


class TestShiftRun(unittest.TestCase):
    def _run_shift(self, tmp):
        runs_dir = os.path.join(tmp, "runs")
        config = Config(inference_backend="mock", runs_dir=runs_dir)
        gate = GateStore(runs_dir)
        fake = _FakeLoop(_shift_records())
        runner = NightShiftRunner(config, fake, gate)
        shift_id = runner.run_shift_sync()
        return runner, gate, fake, shift_id, runs_dir

    def test_designed_night_totals(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner, gate, fake, shift_id, _ = self._run_shift(tmp)
            status = runner.status()
            self.assertEqual(status["shift"]["id"], shift_id)
            self.assertEqual(status["shift"]["state"], "done")

            specs = status["specialists"]
            self.assertAlmostEqual(specs["pricer"]["spent_usd"], 1494.60)
            self.assertAlmostEqual(specs["watcher"]["spent_usd"], 86.97)
            self.assertAlmostEqual(specs["greeter"]["spent_usd"], 214.00)
            self.assertAlmostEqual(status["totals"]["forwarded_usd"],
                                   1795.57)
            self.assertAlmostEqual(status["totals"]["cut_usd"], 660.00)
            self.assertEqual(status["totals"]["runs"], 9)

            cuts = {(c["specialist"], c["title"]) for c in status["cuts"]}
            self.assertEqual(cuts, {("pricer", "Venusaur correction"),
                                    ("watcher",
                                     "Refund DEMO-2077 (claimed non-delivery)")})
            venusaur = next(c for c in status["cuts"]
                            if c["title"] == "Venusaur correction")
            self.assertIn("non-transferable", venusaur["reason"])
            self.assertIn("$1,500.00", venusaur["reason"])

    def test_handoff_through_the_runner_with_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner, gate, fake, shift_id, _ = self._run_shift(tmp)
            status = runner.status()
            self.assertEqual(len(status["handoffs"]), 1)
            handoff = status["handoffs"][0]
            self.assertEqual(handoff["from"], "watcher")
            self.assertEqual(handoff["to"], "pricer")
            self.assertEqual(handoff["source_run_id"], "run-watch-1")
            self.assertEqual(handoff["run_id"], "run-handoff")
            self.assertIn("Charizard", handoff["reason"])
            # The receiving run is the second call, framed as Pricer,
            # carrying the handoff task text and the source run's files.
            self.assertIn("You are the Watcher", fake.calls[0]["task"])
            self.assertIn("You are the Pricer", fake.calls[1]["task"])
            self.assertIn("Reprice Charizard Base Set Holo",
                          fake.calls[1]["task"])
            self.assertIn("orders.csv", fake.calls[1]["seed_files"])

    def test_gate_delivery_and_two_key_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner, gate, fake, shift_id, _ = self._run_shift(tmp)
            delivered = [p for p in gate.state()["proposals"]
                         if str(p.get("source", "")).startswith("nightshift:")]
            self.assertEqual(len(delivered), 8)
            self.assertTrue(all(p["status"] == "pending" for p in delivered))
            by_value = {p["value_usd"]: p for p in delivered}
            # $644.60 and the $500.00 boundary both need two keys.
            sweep = gate.decide(by_value[644.60]["id"], "approve")
            self.assertEqual(sweep["status"], "awaiting_second_key")
            sweep = gate.decide(by_value[644.60]["id"], "approve")
            self.assertEqual(sweep["status"], "approved")
            boundary = gate.decide(by_value[500.00]["id"], "approve")
            self.assertEqual(boundary["status"], "awaiting_second_key")
            # A $0 draft approves on one key.
            draft = gate.decide(by_value[0.0]["id"], "approve")
            self.assertEqual(draft["status"], "approved")

    def test_morning_report_record_replays(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner, gate, fake, shift_id, runs_dir = self._run_shift(tmp)
            report_id = runner.status()["shift"]["report_run_id"]
            self.assertEqual(report_id, f"nightshift-{shift_id}")
            path = Path(runs_dir) / f"{report_id}.json"
            record = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(record["status"], "completed")
            kinds = {e["kind"] for e in record["transcript"]}
            self.assertIn("handoff", kinds)
            self.assertIn("cut", kinds)
            html = replay_page(record)
            self.assertIn("Morning verdict", html)
            self.assertIn("Cut by budget", html)

    def test_tool_subset_audit_records_not_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner, gate, fake, shift_id, _ = self._run_shift(tmp)
            discipline = runner.status()["discipline"]
            self.assertEqual(len(discipline), 1)
            self.assertEqual(discipline[0]["specialist"], "watcher")
            self.assertEqual(discipline[0]["tools_outside_subset"],
                             ["run_shell"])

    def test_state_persists_across_runner_instances(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner, gate, fake, shift_id, runs_dir = self._run_shift(tmp)
            config = Config(inference_backend="mock", runs_dir=runs_dir)
            reloaded = NightShiftRunner(config, _FakeLoop([]), gate)
            self.assertEqual(reloaded.status()["shift"]["state"], "done")
            self.assertEqual(reloaded.status()["shift"]["id"], shift_id)


class TestBudgetMechanics(unittest.TestCase):
    def test_budget_cut_and_invalid_proposal(self):
        fixture = {
            "night": "unit-test night",
            "events": [{
                "id": "only-event", "specialist": "pricer",
                "title": "Big then bigger", "task": "Propose.",
                "files": {},
            }],
        }
        record = _record(answer=_answer(
            {"kind": "reprice", "title": "First move",
             "rows": [{"name": "Big", "price": 100.0, "qty": 14,
                       "new_price": 200.0}]},
            {"kind": "reprice", "title": "Second move",
             "rows": [{"name": "Big", "price": 100.0, "qty": 2,
                       "new_price": 200.0}]},
            {"kind": "wire_money", "title": "Not a real kind",
             "detail": "unpriceable"}), run_id="run-unit")
        with tempfile.TemporaryDirectory() as tmp:
            night_file = Path(tmp) / "night.json"
            night_file.write_text(json.dumps(fixture), encoding="utf-8")
            original = nightshift.NIGHT_FILE
            nightshift.NIGHT_FILE = night_file
            try:
                runs_dir = os.path.join(tmp, "runs")
                config = Config(inference_backend="mock", runs_dir=runs_dir)
                gate = GateStore(runs_dir)
                runner = NightShiftRunner(config, _FakeLoop([record]), gate)
                runner.run_shift_sync()
            finally:
                nightshift.NIGHT_FILE = original
            status = runner.status()
            self.assertAlmostEqual(
                status["specialists"]["pricer"]["spent_usd"], 1400.0)
            self.assertEqual([c["title"] for c in status["cuts"]],
                             ["Second move"])
            self.assertEqual(len(status["invalid"]), 1)
            self.assertIn("unpriceable", status["invalid"][0]["reason"])
            delivered = [p for p in gate.state()["proposals"]
                         if str(p.get("source", "")).startswith("nightshift:")]
            self.assertEqual(len(delivered), 1)


if __name__ == "__main__":
    unittest.main()
