# Phase 2 — Night Shift (spec)

> **STATUS: BUILT Nov 5, 2026** — entry gate met (Gauntlet verified live
> Nov 4); implemented as specced in `agent/app/nightshift.py`, live-verified
> (see BUILD-LOG). This file remains the design record.

**One-line pitch:** Three specialist agents — Pricer, Watcher, Greeter —
work the store overnight inside one sandbox, each with its own blast
budget, handing work to each other on script, and the owner wakes up to a
single morning verdict report.

> **ENTRY GATE:** Build starts only if the Gauntlet is verified live with
> runway to spare; otherwise this stays a spec.

## What a judge sees in 90 seconds

1. The night board: three named specialists clock in — **Pricer**
   (repricing inputs), **Watcher** (orders watch + listing health),
   **Greeter** (buyer-message triage and scan-intake). Each shows its
   **blast budget**: the maximum dollar value of proposals it may
   originate overnight.
2. A scripted night plays out: Watcher flags a price anomaly and hands
   it to Pricer; Greeter drafts replies but cannot send anything; Pricer
   prepares a sweep and hits its budget ceiling mid-prep — the over-
   budget remainder is cut and logged, not smuggled through.
3. Morning: the **verdict report** — what each specialist proposed, what
   was handed off and why, what was cut by budget, and the single list
   waiting at Pocket Gate for human approval. Nothing applied overnight.
   Nothing ever applies overnight.

## Components to add

Nothing below the agent layer changes. Night Shift is three
configurations of BRZ's existing loop, one shared sandbox discipline,
and one report:

- `agent/app/nightshift.py` — the shift runner. Starts each specialist as
  an agent-loop run (`agent/app/loop.py`) with its own system-prompt
  role, tool subset, and blast budget; all tool calls go through the
  existing sandbox client (`agent/app/sandbox_client.py`) — one sandbox
  per run, same hardening, no new execution path.
- Specialist definitions (config, not code forks): Pricer, Watcher,
  Greeter — role prompt, allowed task types drawn from the supporting
  roster (repricing, reconciliation, listing health, orders watch,
  scan-intake triage), and a per-agent blast budget in dollars.
- **Blast budgets, enforced in the runner, not the prompt:** every
  proposal a specialist originates is priced with the Meter's arithmetic;
  the runner keeps a per-agent running total and refuses to forward any
  proposal that would exceed that agent's budget. The refusal is logged
  and appears in the morning report. Budgets are per-agent and
  non-transferable — Pricer cannot spend Watcher's headroom.
- **Scripted handoffs:** a handoff is a run record + a task string passed
  from one specialist's output to the next specialist's intake through
  the runner only (specialists never call each other directly, and no
  handoff executes outside the sandbox). Handoff reasons are recorded
  verbatim in the shift log.
- `GET /nightshift` (page, `agent/app/nightshift_page.py`) — the night
  board: specialists, budgets, spend-so-far per agent, handoff log.
- Morning verdict report: a shift summary run record (proposals per
  agent, budget cuts, handoffs, totals) rendered by the existing replay
  machinery (`GET /replay/<run_id>`) and delivered to Pocket Gate as
  proposals — where the normal rules apply unchanged, including the
  two-key rule for moves ≥ $500.

## Fixtures / data needed

- A scripted night fixture (`agent/app/nightshift_night.json`): the
  overnight event set — market price moves for Pricer, order/listing
  anomalies for Watcher, buyer messages and a scan batch for Greeter,
  at least one cross-specialist handoff trigger, and at least one event
  designed to push a specialist over budget. Frozen and readable, like
  `gauntlet_attacks.json`.
- Demo catalogue/order/message payloads in the existing demo shapes
  (same rows the Meter prices), labelled demo data on every page.
- Budget values for the demo shift, chosen so the over-budget cut
  actually happens on the scripted night.

## Safety tests to add

All in the existing suite style (`python3 tests/run_tests.py`, stdlib
unittest, offline, mock inference):

- Budget enforcement is mechanical: with a mock planner that proposes
  moves past a specialist's budget, assert the over-budget proposal is
  refused by the runner, logged, and absent from the morning report's
  proposal list (present in its cut list).
- Budgets are non-transferable and per-agent: total proposals across the
  shift may exceed one agent's budget only if each agent stayed within
  its own; assert per-agent totals, not just the shift total.
- No overnight application: assert that a full scripted night produces
  proposals and gate entries only — no applied state changes — and that
  a surviving proposal ≥ $500 still needs two approvals at the gate in
  the morning.
- Handoffs go through the runner: assert every handoff in the shift log
  carries a from-agent, a to-agent, a reason, and a run id, and that a
  handoff cannot carry a tool call (task text only).
- Sandbox discipline unchanged: each specialist run's record shows the
  same sandbox backend and containment properties as a normal run
  (reuse the existing containment assertions).

## Honest effort estimate

Medium-large — roughly 2–3 focused build days once the entry gate opens.
The loop and sandbox are reused as-is; the genuinely new work is budget
enforcement in the runner, the handoff plumbing, the night fixture, and
the board page. The risk is scope creep into "real" multi-agent
orchestration — this spec deliberately keeps specialists as loop
configurations with a script, not a framework.

## Entry gate (repeated, because it governs)

Build starts only if the Gauntlet is verified live with runway to spare;
otherwise this stays a spec.
