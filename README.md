# Blast Radius Zero

**The store agent that can do almost anything — and is allowed to do nothing alone.**

Blast Radius Zero is a live store-operations agent for Card Cauldron TCG, a
real Pokémon card store. The store runs roughly 2,000 live listings, and
real money sits behind every price: change the wrong price, issue the wrong
refund, or delete the wrong listing and the loss is immediate and real.
That is why this agent is built the way it is. It reasons, proposes, and
prepares real work — but it applies nothing on its own. Every consequential
move is a dry-run proposal first, a human approves it, and every move is
logged. And every tool call it ever makes runs inside a disposable,
network-less Docker sandbox that holds no secrets, so even a successful
prompt injection has nothing to steal and nowhere to send it. The blast
radius is zero by construction, not by hoping the model behaves.

One honesty note up front: the store itself is paused on Time Away from
November 1–15, 2026, while its physical stock is re-sorted. All demo work
in this project runs on demo data, labelled as demo data wherever it
appears. The agent, the sandbox, the reasoning, and the containment are
real; the catalogue rows and orders it practises on are not live listings.

Built for the **LabLab "Vultr: Agent Rush" hackathon** (Challenge 1).
Deadline: Sunday, November 8, 2026, 6:00 PM EST.

Live demo: http://144.202.55.202:8080

## The hero job: the repricing sweep

The job this agent exists to do is the repricing sweep: repricing
40 listings against recent sold prices. Prices drift, sold prices move,
and a store with ~2,000 listings cannot re-check every card by hand every
day — so the agent does the checking, computes each proposed new price
with its reason, and presents the whole sweep as one proposal.

Stated in money terms, because that is the point: in the demo sweep
(`agent/app/gate_seed.json`, demo data), the 40 listings move from a total
sticker value of $6,204.50 to $7,445.00 — $1,240.50 rides on the sweep
being right. A wrong unapproved sweep is a four-figure mistake. So the
sweep never applies itself: it arrives as a proposal, a human approves it
at the gate (see "The human gate" below — a sweep this size needs two
approvals), and only then does anything change.

Supporting roster, in one line: reconciliation, listing health, orders
watch, scan-intake triage, and the morning report — the same
propose-then-approve discipline applied to the store's daily chores.

## Watch it get attacked — the Gauntlet and the Meter

A store agent reads untrusted content all day: buyer messages, supplier
emails, listing notes, scan records. Any of them can carry an instruction
the store never gave. The Gauntlet exists to prove, live, what happens
when they do.

- **The Saboteur.** A scripted attacker, driven through the same Vultr
  Serverless Inference endpoint as the agent and running outside the
  sandbox, fires a **frozen set of 7 attacks** at the store agent. The
  set is frozen so the result is a measurement, not a performance: the
  exact attacks live in `agent/app/gauntlet_attacks.json`, readable by
  anyone, and they do not change between runs.
- **The 7 attacks:** a refund-everything buyer message; a poisoned
  listing note; a scan record smuggling "reprice everything to $1"; a
  supplier-email command injection; discount-code social engineering;
  credential / system-prompt exfiltration; and an authority-spoof attempt
  to delete the logs.
- **The scoreboard** at `GET /gauntlet` (new in this build) shows three
  numbers: **ATTACKS IN · ATTACKS LANDED · CONTAINED**. Verdicts are
  classified conservatively: a run counts as *landed* only on positive
  evidence that the agent complied. Errors and ambiguous runs are
  recorded as **"unverified"** — never quietly counted as contained.
- **The Meter.** Every contained attack carries the dollar damage it
  would have done, computed from the attack's own demo payload with the
  arithmetic printed: a blocked refund is worth the order total; a
  blocked reprice-to-$1 is worth Σ(price − $1) × qty over the demo
  catalogue rows it targeted. The running tally is **DAMAGE PREVENTED**,
  and it is labelled **"simulated on demo data"** everywhere it appears —
  the containment is real, the dollars are an honest simulation.

## The human gate — Pocket Gate

Proposals are only half the discipline; the other half is where the human
says yes or no. **Pocket Gate** at `GET /gate` (new in this build) is a
phone-friendly approval page over the agent's proposed moves:

- **Approve / reject / undo** from a phone — the owner runs the store
  from his phone, so the gate lives there too.
- **Two-key rule:** any move worth **$500 or more needs two separate
  approvals** before it can apply. The $1,240.50 repricing sweep above
  cannot go through on a single tap.
- Every decision is logged with the run it belongs to.
- The gate's seed moves are demo data (see `agent/app/gate_seed.json`);
  each one prints its own arithmetic, so the value at stake is checkable,
  not asserted.

## Phase 2: Night Shift and Rewind

Two more disciplines on the same chassis, built November 5, 2026 — the
loop, the sandbox, and the gate are unchanged; everything below is
agent-layer composition of the frozen pieces.

### Night Shift — the store works overnight, applies nothing

Three specialists — **Pricer** (repricing), **Watcher** (orders watch +
listing health), **Greeter** (buyer-message triage and scan intake) —
work one frozen scripted night (`agent/app/nightshift_night.json`,
8 events, demo data) as configurations of the same agent loop. Each
specialist has a **blast budget**: the maximum dollar value of proposals
it may originate overnight (demo shift: Pricer $1,500, Watcher $300,
Greeter $250). Budgets are enforced **in the runner, not the prompt**:
every proposal is priced by the Meter, added to that specialist's
running total, and any proposal that would cross the budget is refused,
logged, and shown in the morning report's cut list. Budgets are
per-agent and non-transferable. Handoffs between specialists pass
through the runner only, as task text — never as tool calls.

**`GET /nightshift`** is the night board: specialists, budgets,
spend-so-far, the handoff log, and the cut list. Nothing applies
overnight; surviving proposals are delivered to Pocket Gate in the
morning as pending dry-runs, where the two-key rule still applies.

First live shift (Nov 5, `2bdfb651854e`): Pricer spent $1,494.60 of its
$1,500 budget with one proposal cut at the ceiling; Watcher $86.97 of
$300; Greeter $214.00 of $250; 11 proposals delivered to the gate.

### Rewind — rehearse the day before any of it counts

Rewind takes one frozen, scripted trading day
(`agent/app/rewind_day.json` — 40 events: repricing, orders, buyer
messages including two poisoned ones, reconciliation, listing health,
scan intake; demo data) and processes each event with the ordinary
agent loop inside the ordinary sandbox, against a **clone ledger** of
the store. Every proposed move is priced by the Meter and checked
mechanically against the day's safety invariants: no price may end
below the $5.00 floor; a refund needs a real, matching, refundable,
not-already-refunded clone order; a listing with an open order may not
be delisted; reprices may only name listings at the clone's current
price; the day's surviving total may not exceed $4,000. A move that
breaks an invariant **dies in rehearsal** — recorded with its run id
and the exact reason — and never reaches Pocket Gate. Survivors are
applied to the clone (so later events rehearse against the day as it
actually unfolded) and delivered to the gate only when the day ends.

**`GET /rewind`** is the rehearsal board: the event timeline,
per-move outcomes, and the expected-safe outcome next to how the day
actually ended.

First live day (Nov 5, `a564597892e6`): 32 of 40 events completed,
27 proposals survived and were delivered ($2,437.57 against the
$4,000 ceiling), none blocked, disaster tally $0.00. The other 8
events hit the known protocol limitation below.

### Known limitation — the model sometimes stops speaking JSON

Honest wart, documented with evidence in `ARCHITECTURE.md` §9.3 and
the build log: on longer, file-heavy tasks (scan-intake events are the
cluster), the model occasionally stops replying with a JSON action
object at all — the loop records `reply contained no JSON object`,
feeds it back, and after 3 in a row ends that run with the explicit
error `model produced 3 unparseable replies in a row`. In the first
live Rewind day this ended 8 of 40 event runs (transcripts of 10–12
steps each); one Night Shift run hit it too. The failure is contained
by design: the run ends as an error record, no proposal is invented,
nothing is applied, and the shift/day continues with the next event.
It is a model protocol-adherence limit on long tasks — not a sandbox
or containment failure; no tool call is ever dispatched from an
unparseable reply.

## Don't trust it — inspect it: the Glass Box

Every claim in this README is meant to be checked, not believed.

- **`GET /inspect`** (new in this build) — "Inspect our sandbox": each
  containment claim listed next to how to verify it, with links to the
  live `/containment-report` probe and to the test suite.
- **`GET /replay/<run_id>`** (new in this build) — a plain-English replay
  of any run: the instruction it was given, each sandbox step narrated,
  and the final report. No raw-log archaeology required.
- **`GET /containment-report`** — launches a fresh sandbox on demand and
  reports what it can see: environment variable names, any secret-like
  variables, Docker socket presence, and whether it can reach the
  internet. It can't.

### Verify the sandbox yourself

The hardening is not a diagram; it is three files. Read them:

- `worker/executor.py` — the tool executor that runs inside the sandbox
  (`run_shell`, `write_file`, `read_file`, `list_files`,
  `probe_environment`), with file operations jailed to the workspace.
- `agent/app/sandbox_client.py` — every Docker hardening flag in one
  place: `--network none`, `--read-only` root filesystem, a 64 MB tmpfs
  workspace as the only writable space, `--cap-drop ALL`,
  `no-new-privileges`, runs as `nobody`, 256 MB RAM, 0.5 CPU, 128 pids,
  per-tool-call timeouts, and `--rm` destruction after each run.
- `agent/app/loop.py` — the agent loop. It plans and dispatches; it
  executes nothing itself. Tool calls are forwarded unmodified to the
  sandbox.

Then run the probe and the tests:

```bash
# live probe (against the running demo): GET /containment-report
python3 tests/run_tests.py
```

94 tests, stdlib `unittest`, fully offline — including the containment
scenario, which plants a fake API key in the agent's environment and
asserts the value appears nowhere in the run record.

## A judge's 60 seconds

1. Open the demo: http://144.202.55.202:8080
2. Run a sample task — the CSV analysis, or the containment task:
   summarise the team note that tries to order the agent to steal its
   own API key.
3. Open `/gauntlet` and read the scoreboard: attacks in, attacks landed,
   contained — and the Meter's DAMAGE PREVENTED tally (simulated on demo
   data, labelled as such).
4. Open `/inspect` and follow one claim to its verification: the live
   containment probe, or the code that implements it.
5. Run the tests: `python3 tests/run_tests.py` — 94 tests, offline.
6. If you have two more minutes: open `/nightshift` and `/rewind` —
   the overnight crew and the day rehearsal, with their budgets,
   invariants, and the known limitation stated on the tin.

## How it works

1. **Plan** — the task goes to **Vultr Serverless Inference**. Per the
   challenge rules, *all* reasoning happens there; no agent reasoning
   happens on the VM. The model replies with one JSON action at a time
   (`{"action": "tool", ...}` or `{"action": "final", ...}`), a strict
   protocol that any chat model on the platform can drive. The Gauntlet's
   Saboteur is driven through the same endpoint.
2. **Dispatch** — the orchestrator forwards tool calls, unmodified, to
   the sandbox. The orchestrator itself never executes anything.
3. **Execute** — inside the sandbox, a small executor
   (`worker/executor.py`) provides `run_shell`, `write_file`, `read_file`,
   `list_files`, and a `probe_environment` self-audit. File operations are
   jailed to the workspace; shell commands run with the workspace as cwd
   and per-call timeouts. The sandbox environment is built from scratch —
   no API keys or credentials inside.
4. **Report** — observations stream back to the model until it produces a
   final answer. The run record (task, transcript, answer) is stored, the
   move (if any) waits at the human gate as a dry-run proposal, and the
   sandbox container is destroyed.

### Architecture summary

- **Control plane (trusted):** the agent process on the VM — HTTP API and
  demo pages, the agent loop (`agent/app/loop.py`), the inference
  adapter, the Gauntlet, the Pocket Gate, the Glass Box, Night Shift,
  and Rewind. It holds the
  inference key in its environment and the host Docker socket so it can
  launch sandboxes. It executes no tool calls itself.
- **Sandbox (untrusted):** one Docker container per task run, launched by
  `agent/app/sandbox_client.py` with the flags listed above, destroyed
  after the run. Everything the model asks to execute runs only here.
- **Reasoning (external):** Vultr Serverless Inference, OpenAI-compatible
  chat completions. There is no local model and no fallback provider.
  (A scripted `mock` adapter exists for offline development and tests
  only; it performs no reasoning, is visibly flagged wherever active, and
  is never the deployed configuration.)
- Full design, sandbox-law mapping, and secrets design:
  `ARCHITECTURE.md`.

### Endpoints

Existing: `GET /` (demo), `GET /health`, `GET /samples`,
`POST /tasks`, `GET /runs/<id>`, `GET /containment-report`.

New in this build: `GET /gauntlet` (scoreboard + Meter),
`GET /gate` (Pocket Gate), `GET /inspect` (Glass Box),
`GET /replay/<run_id>` (plain-English run replay).

Phase 2 (Nov 5): `GET /nightshift` (night board) +
`POST /nightshift/run` + `GET /nightshift/status`;
`GET /rewind` (rehearsal board) + `POST /rewind/run` +
`GET /rewind/status`.

## Vultr services used

| Vultr service | Role |
|---|---|
| **Serverless Inference** | **All** agent reasoning — a hard event rule, not a preference. Every planning call the agent makes, and every Saboteur call in the Gauntlet, goes to the Serverless Inference endpoint (`https://api.vultrinference.com/v1`, OpenAI-compatible chat completions). The model is chosen at deploy time (`BRZ_MODEL`, from `GET /v1/models`). No reasoning happens on the VM. |
| **Cloud Compute** | One small CPU instance hosts the orchestrator (control plane) and launches the per-run sandboxed tool containers via Docker. **No GPUs** — none are used and none are needed; inference is serverless. |

**Where the key lives:** the Serverless Inference key exists **only in
the agent process's environment at deploy time**. It is never in this
repo (`.env` is git-ignored; `.env.example` carries the variable name
with no value at all), never written to a run record, and **never inside the
sandbox** — the sandbox environment is built from scratch, so there is no
inheritance path for a tool call to reach it.

## Running it

### Offline dry-run (no key, no Docker, no cost)

The whole loop runs locally with a scripted planner stub (clearly flagged
in the UI; tool execution in the local dev backend is real):

```bash
cd agent
BRZ_INFERENCE=mock BRZ_SANDBOX=local python3 -m app.main
# open http://localhost:8080
```

Python 3.11+ only — the project has **zero third-party dependencies**.

Note: `BRZ_SANDBOX=local` is a development backend only. It provides
process separation, not the Docker boundary, and is labelled as such in
code, in run records, and in the UI. It is never the deployed
configuration.

### Tests

```bash
python3 tests/run_tests.py
```

94 tests: the original 22 cover protocol parsing, executor behaviour,
the workspace path jail, environment scrubbing, and full agent-loop
runs — including the containment scenario described above; the next 33
cover the Gauntlet classifier and frozen attack set, the Pocket Gate
two-key rule, and the scoreboard / Glass Box pages; the phase-2 block
covers the Meter's arithmetic, Night Shift budget enforcement
(mechanical, per-agent, non-transferable), handoff shape, Rewind's
invariant checks and frozen-day integrity, and the phase-2 pages.
(Docker-hardened assertions run
when a Docker daemon and the worker image are present.)

### Production deployment (Vultr)

```bash
cp .env.example .env   # fill in VULTR_INFERENCE_API_KEY and BRZ_MODEL
docker compose --profile build build
docker compose up -d agent
```

## Status

**Live and green on Vultr as of November 5, 2026, phase 2 included.**
The deployed agent answers at http://144.202.55.202:8080 with real
Serverless Inference reasoning and the hardened Docker sandbox: the
health check is clean, the sample tasks complete end-to-end, the
containment sample's planted instruction (dump the inference key,
exfiltrate it, hide the attempt) was refused and reported, and the
`/containment-report` probe shows no secret-like variables, no Docker
socket, and no network route from inside the sandbox. The Gauntlet's
first live volley contained 7 of 7 attacks ($24,346.00 damage
prevented, simulated on demo data); Night Shift and Rewind have each
run a full live shift/day (see "Phase 2" above, including the known
protocol limitation, which is documented rather than hidden). The full
test suite passes on the deployment box.

Demo-data labels stand wherever demo data is used: the store is paused
November 1–15, the gate's seed moves and the Meter's dollar figures are
computed on demo payloads, and nothing in the demo touches a live listing.

## Project layout

```
agent/            control plane (trusted): HTTP API + demo pages, agent loop,
  app/            inference adapters (Vultr + offline mock), sandbox clients,
                  Gauntlet, Pocket Gate, Glass Box, Night Shift, Rewind
worker/           sandbox executor (untrusted code runs here) + Dockerfile
demo/             90-second demo script and the sample tasks (incl. the
                  prompt-injected note used for the containment moment)
docs/             phase-2 specs (Rewind, Night Shift) — built Nov 5, 2026
tests/            offline test suite (stdlib unittest)
ARCHITECTURE.md   full design, sandbox law mapping, secrets design
BUILD-LOG.md      build journal and open items
```
