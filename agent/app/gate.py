"""Pocket Gate — the human gate for Blast Radius Zero, made portable.

Pocket Gate is a phone-friendly approve / reject / undo view over the
moves the Blast Radius Zero (BRZ) store-ops agent proposes. BRZ dry-runs
everything it wants to do; nothing is applied until a human decides here.
Approving a proposal in this queue changes NOTHING outside this queue:
the proposals shipped in ``gate_seed.json`` are demo data, and BRZ
applies nothing without this gate — the gate is the product.

Two-key rule: any move worth ``TWO_KEY_THRESHOLD_USD`` or more needs two
separate approvals before it counts as approved. Big moves can't slip
through on one tired tap — a single mistaken or hurried tap on a phone
can only start a high-dollar move, never finish it. Smaller moves need
one approval, and any move can be rejected with a single key. Any
decided (or half-decided) move can be undone back to pending, which
records a fresh undo token in its history.

Standard library only.
"""

import copy
import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

TWO_KEY_THRESHOLD_USD = 500.0

_TWO_KEY_RULE = (
    "Moves of $500 or more need two separate approvals: the first "
    "approval moves a proposal to awaiting_second_key, and only a "
    "second, separate approval marks it approved. Smaller moves need "
    "one approval. Rejection always takes a single key, and any "
    "decided move can be undone back to pending."
)

_SEED_FILE = Path(__file__).resolve().parent / "gate_seed.json"

_VALID_DECISIONS = ("approve", "reject", "undo")
_DECIDED = ("approved", "rejected")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class GateStore:
    """Thread-safe, file-backed store for Pocket Gate proposals.

    State lives in ``Path(runs_dir) / "gate_state.json"``. If that file
    already exists it is loaded; otherwise the store seeds itself from
    ``gate_seed.json`` (beside this module) on first use and persists
    the seeded state. Every mutation happens under a lock and is
    persisted to disk before the call returns.
    """

    def __init__(self, runs_dir: str) -> None:
        self._runs_dir = Path(runs_dir)
        self._state_file = self._runs_dir / "gate_state.json"
        self._lock = threading.Lock()
        self._proposals: list = []
        self._runs_dir.mkdir(parents=True, exist_ok=True)
        if self._state_file.exists():
            self._load()
        else:
            self._seed()
            self._persist()

    # -- internal helpers -------------------------------------------------

    def _load(self) -> None:
        raw = json.loads(self._state_file.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            proposals = raw.get("proposals", [])
        else:
            proposals = raw
        self._proposals = copy.deepcopy(list(proposals))

    def _seed(self) -> None:
        raw = json.loads(_SEED_FILE.read_text(encoding="utf-8"))
        proposals = []
        for item in raw:
            proposals.append({
                "id": item["id"],
                "title": item["title"],
                "detail": item["detail"],
                "value_usd": float(item["value_usd"]),
                "status": "pending",
                "history": [],
            })
        self._proposals = proposals

    def _persist(self) -> None:
        self._runs_dir.mkdir(parents=True, exist_ok=True)
        payload = {"proposals": self._proposals}
        tmp = self._state_file.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                       encoding="utf-8")
        tmp.replace(self._state_file)

    def _find(self, proposal_id: str) -> dict:
        for proposal in self._proposals:
            if proposal.get("id") == proposal_id:
                return proposal
        raise KeyError(proposal_id)

    @staticmethod
    def _record(proposal: dict, action: str, note: str, **extra) -> None:
        entry = {"ts": _now_iso(), "action": action, "note": note}
        entry.update(extra)
        proposal.setdefault("history", []).append(entry)

    # -- public API -------------------------------------------------------

    def state(self) -> dict:
        with self._lock:
            return {
                "threshold_usd": TWO_KEY_THRESHOLD_USD,
                "two_key_rule": _TWO_KEY_RULE,
                "proposals": copy.deepcopy(self._proposals),
            }

    def decide(self, proposal_id: str, decision: str) -> dict:
        """Apply ``decision`` to a proposal and return the updated proposal.

        ``decision`` is one of "approve", "reject", "undo". See the module
        docstring for the two-key rule. Raises KeyError for an unknown
        proposal id and ValueError for an unknown decision or a decision
        that is not valid from the proposal's current status.
        """
        if decision not in _VALID_DECISIONS:
            raise ValueError(f"unknown decision: {decision!r}")
        with self._lock:
            proposal = self._find(proposal_id)
            status = proposal.get("status", "pending")
            value = float(proposal.get("value_usd", 0.0))

            if decision == "approve":
                if status in _DECIDED:
                    raise ValueError("already decided; undo first")
                if status == "pending":
                    if value >= TWO_KEY_THRESHOLD_USD:
                        proposal["status"] = "awaiting_second_key"
                        self._record(
                            proposal, "approve_key_1",
                            "First key: approved, awaiting second key "
                            "(value at or above the two-key threshold).")
                    else:
                        proposal["status"] = "approved"
                        self._record(proposal, "approve", "Approved.")
                elif status == "awaiting_second_key":
                    proposal["status"] = "approved"
                    self._record(
                        proposal, "approve_key_2",
                        "Second key: approved.")
                else:  # pragma: no cover - defensive
                    raise ValueError(f"cannot approve from status {status!r}")
            elif decision == "reject":
                if status in _DECIDED:
                    raise ValueError("already decided; undo first")
                if status in ("pending", "awaiting_second_key"):
                    proposal["status"] = "rejected"
                    self._record(proposal, "reject", "Rejected.")
                else:  # pragma: no cover - defensive
                    raise ValueError(f"cannot reject from status {status!r}")
            else:  # undo
                if status == "pending":
                    raise ValueError("nothing to undo")
                if status in ("approved", "rejected", "awaiting_second_key"):
                    token = uuid.uuid4().hex
                    proposal["status"] = "pending"
                    self._record(
                        proposal, "undo",
                        "Undone; returned to pending.",
                        token=token)
                else:  # pragma: no cover - defensive
                    raise ValueError(f"cannot undo from status {status!r}")

            self._persist()
            return copy.deepcopy(proposal)

    def add_proposal(self, title: str, detail: str, value_usd: float,
                     proposal_id: str | None = None,
                     source: str = "") -> dict:
        """Add a new pending proposal and return it.

        This is how BRZ's own runners (Night Shift, Rewind) deliver the
        moves they originated: always as ``pending`` dry-runs, priced by
        the caller with the Meter's arithmetic printed in ``detail``.
        Adding a proposal changes nothing outside this queue — the same
        approve / reject / undo rules, including the two-key rule for
        moves at or above the threshold, apply to it unchanged. Raises
        ValueError on an empty title, a negative value, or a duplicate
        id.
        """
        if not isinstance(title, str) or not title.strip():
            raise ValueError("proposal title must be a non-empty string")
        value = float(value_usd)
        if value < 0:
            raise ValueError("proposal value cannot be negative")
        with self._lock:
            pid = proposal_id or f"prop-{uuid.uuid4().hex[:10]}"
            if any(p.get("id") == pid for p in self._proposals):
                raise ValueError(f"duplicate proposal id: {pid!r}")
            proposal = {
                "id": pid,
                "title": title,
                "detail": detail,
                "value_usd": round(value, 2),
                "status": "pending",
                "history": [],
            }
            if source:
                proposal["source"] = source
            self._record(proposal, "proposed",
                         source or "Proposed; awaiting a human decision.")
            self._proposals.append(proposal)
            self._persist()
            return copy.deepcopy(proposal)
