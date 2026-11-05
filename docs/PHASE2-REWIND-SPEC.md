# Phase 2 — Rewind (spec)

> **STATUS: BUILT Nov 5, 2026** — entry gate met (Gauntlet verified live
> Nov 4); implemented as specced in `agent/app/rewind.py`, live-verified
> (see BUILD-LOG), including the documented protocol limitation in
> ARCHITECTURE §9.3. This file remains the design record.

**One-line pitch:** Before the agent proposes anything for the real store,
it rehearses the whole day in a cloned fake store — and only the moves
that survive rehearsal are allowed to become proposals.

> **ENTRY GATE:** Build starts only if the Gauntlet is verified live with
> runway to spare; otherwise this stays a spec.

## What a judge sees in 90 seconds

1. A "Rewind the day" button. The agent loads a scripted day of ~40 store
   events — orders, buyer messages (two of them poisoned), price moves in
   the market, a supplier email, a scan batch — into a cloned fake store.
2. The day plays out fast-forward inside the sandbox: the agent works the
   events, makes its mistakes in the clone, and the disasters are caught
   on camera — a bad reprice, a refund that should never have been
   proposed — each priced on the Meter rules.
3. The rehearsal ends and the real proposal list appears: only the moves
   that survived rehearsal, each stamped with its rehearsal outcome.
   The moves that died in the clone are shown too, greyed out, with the
   reason they died. Nothing reaches Pocket Gate that rehearsal killed.

## Components to add

Nothing below the agent layer changes. Rewind is built entirely from
BRZ's existing loop, sandbox, and gates:

- `agent/app/rewind.py` — the rehearsal runner. Takes a scripted day
  (event list), seeds a cloned fake store into a fresh sandbox workspace,
  runs the existing agent loop (`agent/app/loop.py`) against the clone,
  and diffs the clone's end state against the day's expected-safe state.
- `agent/app/rewind_day.json` — the frozen scripted day: ~40 events with
  ids, in the same spirit as `gauntlet_attacks.json` — readable by
  anyone, frozen so rehearsal results are comparable across runs.
- Clone store fixture format: the same catalogue/order rows the Meter and
  Pocket Gate already use (demo payloads), so a move's price in rehearsal
  is computed by the same arithmetic as its price at the gate.
- `GET /rewind` (page, `agent/app/rewind_page.py`) — run/replay a
  rehearsal: event timeline, per-move outcome (survived / died in
  rehearsal, with reason), disaster tally.
- Proposal filter: the loop's dry-run proposals pass through the
  rehearsal verdict before they are written to Pocket Gate
  (`GET /gate`). A proposal with no surviving rehearsal twin does not
  reach the gate; a proposal whose rehearsal twin died is listed as
  blocked, with the rehearsal run id attached.
- Replay integration: every rehearsal is a normal run record, so
  `GET /replay/<run_id>` narrates it with no new machinery.

## Fixtures / data needed

- `rewind_day.json`: ~40 events covering the supporting roster
  (repricing inputs, reconciliation rows, listing-health flags, orders,
  scan-intake records, two injected attacks reusing Gauntlet payloads).
- A clone-store seed: demo catalogue + demo orders, same shapes as
  `agent/app/gate_seed.json` and the Gauntlet demo payloads. Demo data,
  labelled as such on the page.
- An expected-safe end state per event (or per day): which moves may
  exist after rehearsal, which must not, and the dollar ceiling the
  day's total proposed value may not exceed.

## Safety tests to add

All in the existing suite style (`python3 tests/run_tests.py`, stdlib
unittest, offline, mock inference):

- A rehearsal run never writes outside the sandbox workspace: the clone
  is seed files only; assert no path outside the run's workspace is
  touched (the existing path-jail tests are the model).
- A move killed in rehearsal cannot reach the gate: drive the scripted
  day with a mock planner that proposes the known-bad reprice; assert
  the gate's proposal list does not contain it and the blocked list does,
  with the rehearsal run id attached.
- Disaster pricing matches the Meter: for the day's priced disasters,
  assert the rehearsal tally equals the Meter's arithmetic on the same
  payloads (refund = order total; reprice-to-$1 =
  Σ(price − $1) × qty).
- Rehearsal is not a back door around the two-key rule: a surviving
  proposal ≥ $500 still needs two approvals at the gate. Assert the gate
  state, not just the rehearsal verdict.
- Frozen-day integrity: the day file's event count and ids are asserted
  in a test, so the fixture cannot silently shrink.

## Honest effort estimate

Medium — roughly 1.5–2 focused build days once the entry gate opens.
The loop, sandbox, gate, Meter arithmetic, and replay all exist; the new
work is the day fixture (the slow part — 40 events that are interesting
without being rigged), the clone-state diff, and the page. No new
infrastructure, no changes below the agent layer.

## Entry gate (repeated, because it governs)

Build starts only if the Gauntlet is verified live with runway to spare;
otherwise this stays a spec.
