"""Night Shift — three specialist agents work the store overnight.

What it is
----------
Three specialists — **Pricer**, **Watcher**, **Greeter** — work one
scripted demo night (``nightshift_night.json``, frozen) inside the same
sandbox discipline as every other Blast Radius Zero run. Each is a
configuration of the existing agent loop (app/loop.py): a role framed in
its task text, a declared tool subset, and its own **blast budget** —
the maximum dollar value of proposals it may originate overnight.

Budgets are enforced HERE, in the runner, never in the prompt: every
proposal a specialist originates is priced by the Meter
(app/meter.py) and added to that specialist's running total; a proposal
that would cross the budget is refused — logged, shown on the night
board, and listed in the morning report's cut list. Budgets are
per-agent and non-transferable: Pricer cannot spend Watcher's headroom.

Handoffs go through the runner only: a handoff is a task string plus
the source run's working files, passed from one specialist's completed
run to the next specialist's intake. Specialists never call each other,
and a handoff carries text only — never a tool call. The reason is
recorded verbatim in the shift log.

Nothing is applied overnight. Surviving proposals are delivered to
Pocket Gate when the shift ends, as pending dry-runs, where the normal
rules apply unchanged — including the two-key rule for moves >= $500.
The shift also writes a morning verdict run record, so the existing
replay machinery (GET /replay/<run_id>) narrates the whole night.

Tool subsets are declared per specialist and audited, not intercepted:
the loop is shared, frozen infrastructure, so after each run the runner
checks the run's transcript and records any tool call outside the
specialist's subset as a discipline note on the board. The hard walls
remain where they always were — the sandbox, the budget, the gate.

Standard library only.
"""

import copy
import json
import threading
import time
import uuid
from pathlib import Path

from . import meter
from .proposals import PROPOSAL_BLOCK_INSTRUCTIONS, extract_proposals

NIGHT_FILE = Path(__file__).resolve().with_name("nightshift_night.json")

SPECIALISTS = {
    "pricer": {
        "name": "Pricer",
        "role": (
            "You are the Pricer, one of three overnight specialists for "
            "Card Cauldron TCG, a demo Pokemon card store. Your job is "
            "repricing: comparing listings against sold prices and "
            "proposing price moves. You propose; you never apply."),
        "task_types": ["repricing"],
        "budget_usd": 1500.0,
        "tools": ["list_files", "read_file", "write_file", "run_shell"],
    },
    "watcher": {
        "name": "Watcher",
        "role": (
            "You are the Watcher, one of three overnight specialists for "
            "Card Cauldron TCG, a demo Pokemon card store. Your job is "
            "the orders watch and listing health: you spot anomalies, "
            "stale listings and claims, and flag them. You propose; "
            "you never apply."),
        "task_types": ["orders watch", "listing health", "reconciliation"],
        "budget_usd": 300.0,
        "tools": ["list_files", "read_file", "write_file"],
    },
    "greeter": {
        "name": "Greeter",
        "role": (
            "You are the Greeter, one of three overnight specialists "
            "for Card Cauldron TCG, a demo Pokemon card store. Your job "
            "is buyer-message triage and scan-intake. You draft replies "
            "but you cannot send anything; a draft is not a store move."),
        "task_types": ["buyer-message triage", "scan-intake triage"],
        "budget_usd": 250.0,
        "tools": ["list_files", "read_file", "write_file"],
    },
}


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _money(value: float) -> str:
    return f"${value:,.2f}"


def load_night() -> dict:
    """Load and validate the frozen scripted night.

    Raises ValueError on any violation: missing events, duplicate ids,
    an unknown specialist, a malformed event, or a malformed handoff.
    """
    try:
        raw = json.loads(NIGHT_FILE.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read night fixture {NIGHT_FILE}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"night fixture is not valid JSON: {exc}") from exc
    if isinstance(raw, dict):
        events = raw.get("events")
        label = raw.get("night", "")
    else:
        events, label = raw, ""
    if not isinstance(events, list) or not events:
        raise ValueError("night fixture must contain a non-empty 'events' list")
    seen = set()
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("each night event must be an object")
        for key in ("id", "specialist", "title", "task", "files"):
            if key not in event:
                raise ValueError(f"night event {event.get('id', '?')!r} "
                                 f"is missing key {key!r}")
        if event["id"] in seen:
            raise ValueError(f"duplicate night event id: {event['id']!r}")
        seen.add(event["id"])
        if event["specialist"] not in SPECIALISTS:
            raise ValueError(f"night event {event['id']!r}: unknown "
                             f"specialist {event['specialist']!r}")
        if not isinstance(event["files"], dict):
            raise ValueError(f"night event {event['id']!r}: 'files' must "
                             f"be an object of name -> content")
        handoff = event.get("handoff")
        if handoff is not None:
            if not isinstance(handoff, dict) \
                    or handoff.get("to") not in SPECIALISTS \
                    or not isinstance(handoff.get("reason"), str) \
                    or not handoff["reason"].strip() \
                    or not isinstance(handoff.get("task"), str) \
                    or not handoff["task"].strip():
                raise ValueError(f"night event {event['id']!r}: handoff "
                                 f"needs a known 'to', a 'reason' and a "
                                 f"'task' (text only)")
            if handoff["to"] == event["specialist"]:
                raise ValueError(f"night event {event['id']!r}: handoff "
                                 f"to self is not a handoff")
    return {"night": label, "events": events}


class NightShiftRunner:
    """Runs one scripted night across the three specialists.

    ``config`` is an app.config.Config; ``agent_loop`` an
    app.loop.AgentLoop; ``gate_store`` an app.gate.GateStore that
    receives the morning's surviving proposals. State is persisted
    after every event to Path(config.runs_dir)/"nightshift_state.json"
    and reloaded at construction, like the Gauntlet's scoreboard.
    """

    def __init__(self, config, agent_loop, gate_store):
        self._config = config
        self._agent_loop = agent_loop
        self._gate = gate_store
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._state_path = Path(config.runs_dir) / "nightshift_state.json"
        self._state = self._load_state()

    # -- state handling -------------------------------------------------

    def _empty_state(self) -> dict:
        return {
            "shift": {"id": None, "state": "idle", "started_at": None,
                      "finished_at": None, "report_run_id": None},
            "specialists": {
                key: {"name": spec["name"], "budget_usd": spec["budget_usd"],
                      "spent_usd": 0.0, "forwarded": 0, "cut": 0}
                for key, spec in SPECIALISTS.items()
            },
            "events": [],
            "handoffs": [],
            "proposals": [],
            "cuts": [],
            "invalid": [],
            "discipline": [],
            "totals": {"forwarded_usd": 0.0, "cut_usd": 0.0, "runs": 0},
        }

    def _load_state(self) -> dict:
        try:
            raw = json.loads(self._state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self._empty_state()
        state = self._empty_state()
        if isinstance(raw, dict):
            for key in state:
                if key in raw:
                    state[key] = raw[key]
        return state

    def _persist_locked(self) -> None:
        """Write state to disk. Caller must hold self._lock."""
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self._state_path.with_suffix(".json.tmp")
            tmp_path.write_text(
                json.dumps(self._state, indent=2, ensure_ascii=False),
                encoding="utf-8")
            tmp_path.replace(self._state_path)
        except OSError:
            pass  # persistence is best-effort; the in-memory state stands

    # -- public API -----------------------------------------------------

    def status(self) -> dict:
        with self._lock:
            return copy.deepcopy(self._state)

    def start_shift(self) -> str:
        """Start a shift on a daemon thread; return its shift id.

        If a shift is already running, return the running shift's id
        without starting a second one.
        """
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return self._state["shift"]["id"]
        shift_id = self._begin_shift()
        thread = threading.Thread(target=self._execute_shift,
                                  name=f"nightshift-{shift_id}", daemon=True)
        with self._lock:
            self._thread = thread
        thread.start()
        return shift_id

    def run_shift_sync(self) -> str:
        """Run a full shift in the calling thread; return the shift id."""
        self._begin_shift()
        self._execute_shift()
        with self._lock:
            return self._state["shift"]["id"]

    # -- shift internals --------------------------------------------------

    def _begin_shift(self) -> str:
        shift_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._state = self._empty_state()
            self._state["shift"] = {
                "id": shift_id, "state": "running",
                "started_at": _utc_now(), "finished_at": None,
                "report_run_id": None,
            }
            self._persist_locked()
        return shift_id

    def _execute_shift(self) -> None:
        night = load_night()
        try:
            for event in night["events"]:
                record = self._work_event(event, via_handoff_from=None)
                handoff = event.get("handoff")
                if handoff:
                    self._run_handoff(event, record, handoff)
        finally:
            self._finish_shift()

    def _run_handoff(self, source_event: dict, source_record: dict,
                     handoff: dict) -> None:
        follow_up = {
            "id": f"{source_event['id']}->handoff",
            "specialist": handoff["to"],
            "title": f"Handoff from {SPECIALISTS[source_event['specialist']]['name']}: "
                     f"{source_event['title']}",
            "task": handoff["task"],
            "files": dict(source_event["files"]),
        }
        record = self._work_event(follow_up,
                                  via_handoff_from=source_event["id"])
        entry = {
            "from": source_event["specialist"],
            "to": handoff["to"],
            "reason": handoff["reason"],
            "source_event": source_event["id"],
            "source_run_id": source_record.get("id"),
            "run_id": record.get("id"),
        }
        with self._lock:
            self._state["handoffs"].append(entry)
            self._persist_locked()

    def _work_event(self, event: dict, via_handoff_from: str | None) -> dict:
        spec = SPECIALISTS[event["specialist"]]
        task_text = (
            f"{spec['role']}\n\nTask: {event['task']}\n"
            f"{PROPOSAL_BLOCK_INSTRUCTIONS}"
        )
        try:
            record = self._agent_loop.run(task_text,
                                          seed_files=dict(event["files"]))
        except Exception as exc:  # the loop records its own errors; belt
            record = {"id": None, "status": "error", "answer": None,  # braces
                      "transcript": [],
                      "error": f"{type(exc).__name__}: {exc}",
                      "sandbox_backend": None}
        priced, cuts, invalid = self._price_and_budget(event, record)
        self._audit_tools(event, record)
        entry = {
            "event_id": event["id"],
            "specialist": event["specialist"],
            "title": event["title"],
            "run_id": record.get("id"),
            "run_status": record.get("status"),
            "sandbox_backend": record.get("sandbox_backend"),
            "via_handoff_from": via_handoff_from,
            "proposals": [p["title"] for p in priced],
        }
        with self._lock:
            self._state["events"].append(entry)
            self._state["totals"]["runs"] += 1
            self._persist_locked()
        return record

    def _price_and_budget(self, event: dict, record: dict):
        """Price a run's proposals with the Meter; enforce the budget.

        Returns (forwarded, cuts, invalid) for this event and updates the
        shift state under the lock. A proposal that would cross the
        specialist's budget is refused here — mechanically, whatever the
        model intended.
        """
        key = event["specialist"]
        forwarded, cuts, invalid = [], [], []
        for payload in extract_proposals(record.get("answer")):
            try:
                priced = meter.price_proposal(payload)
            except ValueError as exc:
                invalid.append({
                    "specialist": key, "event_id": event["id"],
                    "run_id": record.get("id"),
                    "title": str(payload.get("title", "<untitled>")),
                    "reason": f"unpriceable proposal, not forwarded: {exc}",
                })
                continue
            item = {
                "specialist": key,
                "event_id": event["id"],
                "run_id": record.get("id"),
                "kind": payload.get("kind"),
                "title": payload["title"],
                "detail": str(payload.get("detail", "")),
                "value_usd": priced["value_usd"],
                "arithmetic": priced["arithmetic"],
            }
            with self._lock:
                spent = self._state["specialists"][key]["spent_usd"]
                budget = self._state["specialists"][key]["budget_usd"]
                if spent + priced["value_usd"] > budget:
                    item["reason"] = (
                        f"would take {SPECIALISTS[key]['name']} to "
                        f"{_money(spent + priced['value_usd'])} of "
                        f"proposals, over its {_money(budget)} blast "
                        f"budget (headroom {_money(budget - spent)}). "
                        f"Budgets are per-agent and non-transferable.")
                    cuts.append(item)
                    self._state["cuts"].append(item)
                    self._state["specialists"][key]["cut"] += 1
                    self._state["totals"]["cut_usd"] = round(
                        self._state["totals"]["cut_usd"]
                        + priced["value_usd"], 2)
                else:
                    forwarded.append(item)
                    self._state["proposals"].append(item)
                    self._state["specialists"][key]["spent_usd"] = round(
                        spent + priced["value_usd"], 2)
                    self._state["specialists"][key]["forwarded"] += 1
                    self._state["totals"]["forwarded_usd"] = round(
                        self._state["totals"]["forwarded_usd"]
                        + priced["value_usd"], 2)
                self._persist_locked()
        with self._lock:
            self._state["invalid"].extend(invalid)
            self._persist_locked()
        return forwarded, cuts, invalid

    def _audit_tools(self, event: dict, record: dict) -> None:
        """Record any tool call outside the specialist's declared subset."""
        allowed = set(SPECIALISTS[event["specialist"]]["tools"])
        used = {entry.get("tool") for entry in record.get("transcript") or []
                if entry.get("kind") == "tool" and entry.get("tool")}
        outside = sorted(used - allowed)
        if outside:
            with self._lock:
                self._state["discipline"].append({
                    "specialist": event["specialist"],
                    "event_id": event["id"],
                    "run_id": record.get("id"),
                    "tools_outside_subset": outside,
                    "note": "declared subset is a soft layer; the run "
                            "stayed inside the sandbox and its proposals "
                            "still faced the budget and the gate",
                })
                self._persist_locked()

    def _finish_shift(self) -> None:
        """Deliver survivors to Pocket Gate; write the morning record."""
        with self._lock:
            shift_id = self._state["shift"]["id"]
            proposals = copy.deepcopy(self._state["proposals"])
            cuts = copy.deepcopy(self._state["cuts"])
            handoffs = copy.deepcopy(self._state["handoffs"])
            specialists = copy.deepcopy(self._state["specialists"])
            totals = copy.deepcopy(self._state["totals"])

        gate_ids = []
        for i, item in enumerate(proposals, start=1):
            detail = (
                f"Night Shift proposal (demo data) from "
                f"{SPECIALISTS[item['specialist']]['name']}, run "
                f"{item['run_id']}. {item['detail']} "
                f"Arithmetic: {item['arithmetic']}"
            )
            added = self._gate.add_proposal(
                title=item["title"], detail=detail,
                value_usd=item["value_usd"],
                proposal_id=f"ns-{shift_id[:6]}-{i:02d}",
                source=f"nightshift:{shift_id}")
            gate_ids.append(added["id"])

        report_id = self._write_morning_record(shift_id, proposals, cuts,
                                               handoffs, specialists, totals)
        with self._lock:
            self._state["shift"]["state"] = "done"
            self._state["shift"]["finished_at"] = _utc_now()
            self._state["shift"]["report_run_id"] = report_id
            self._state["delivered_to_gate"] = gate_ids
            self._persist_locked()

    def _write_morning_record(self, shift_id, proposals, cuts, handoffs,
                              specialists, totals) -> str:
        """A run-record-shaped morning verdict, for GET /replay/<id>."""
        lines = [
            "Morning verdict — Night Shift "
            f"{shift_id} (demo data throughout).",
            "",
        ]
        for key, s in specialists.items():
            lines.append(
                f"{s['name']}: budget {_money(s['budget_usd'])}, proposed "
                f"{_money(s['spent_usd'])} across {s['forwarded']} "
                f"forwarded proposal(s), {s['cut']} cut.")
        lines.append("")
        lines.append("Proposals waiting at Pocket Gate (nothing applied "
                     "overnight):")
        for item in proposals:
            lines.append(f"- [{SPECIALISTS[item['specialist']]['name']}] "
                         f"{item['title']} — {_money(item['value_usd'])}. "
                         f"{item['arithmetic']}")
        if cuts:
            lines.append("")
            lines.append("Cut by budget (refused by the runner, logged):")
            for item in cuts:
                lines.append(f"- [{SPECIALISTS[item['specialist']]['name']}] "
                             f"{item['title']} — "
                             f"{_money(item['value_usd'])}. {item['reason']}")
        if handoffs:
            lines.append("")
            lines.append("Handoffs:")
            for h in handoffs:
                lines.append(f"- {SPECIALISTS[h['from']]['name']} -> "
                             f"{SPECIALISTS[h['to']]['name']}: {h['reason']}")
        answer = "\n".join(lines)

        transcript = []
        step = 0
        with self._lock:
            events = copy.deepcopy(self._state["events"])
        for entry in events:
            step += 1
            transcript.append({
                "step": step, "kind": "event", "ok": True,
                "observation": (
                    f"{SPECIALISTS[entry['specialist']]['name']} worked "
                    f"'{entry['title']}' (run {entry['run_id']}, status "
                    f"{entry['run_status']}) and originated: "
                    f"{', '.join(entry['proposals']) or 'no proposals'}."),
            })
        for h in handoffs:
            step += 1
            transcript.append({
                "step": step, "kind": "handoff", "ok": True,
                "observation": (
                    f"{SPECIALISTS[h['from']]['name']} handed work to "
                    f"{SPECIALISTS[h['to']]['name']} through the runner: "
                    f"{h['reason']}"),
            })
        for item in cuts:
            step += 1
            transcript.append({
                "step": step, "kind": "cut", "ok": True,
                "observation": (
                    f"Budget cut — {item['title']} "
                    f"({_money(item['value_usd'])}): {item['reason']}"),
            })

        record = {
            "id": f"nightshift-{shift_id}",
            "task": "Night Shift: three specialists (Pricer, Watcher, "
                    "Greeter) work one scripted demo night; the morning "
                    "verdict report.",
            "status": "completed",
            "answer": answer,
            "error": None,
            "sandbox_backend": "see per-event runs",
            "inference_backend": self._config.inference_backend,
            "model": self._config.model or None,
            "started_at": None,
            "finished_at": _utc_now(),
            "transcript": transcript,
        }
        try:
            runs_dir = Path(self._config.runs_dir)
            runs_dir.mkdir(parents=True, exist_ok=True)
            (runs_dir / f"{record['id']}.json").write_text(
                json.dumps(record, indent=2, ensure_ascii=False),
                encoding="utf-8")
        except OSError:
            pass  # best-effort, like the loop's own persistence
        return record["id"]
