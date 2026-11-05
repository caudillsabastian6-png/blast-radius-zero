# Demo video script — ≤90 seconds

Blast Radius Zero, LabLab "Vultr: Agent Rush" submission video. Everything
shown is the live public demo — no mockups, no staged screenshots. Demo
data is labelled on screen wherever it appears.

Live demo: http://144.202.55.202:8080

## Timed beats

**0:00–0:05 — The stakes**
Screen: the store, then one line of text, full screen:
"A real card store. ~2,000 live listings. Real money."
Narration: "This is a real card store. Two thousand live listings — and
real money behind every price."

**0:05–0:30 — The Gauntlet volley**
Screen: `GET /gauntlet`. The frozen set of 7 attacks fires at the store
agent in sequence — the refund-everything buyer message, the poisoned
listing note, the scan record smuggling "reprice everything to $1", the
supplier-email injection, the discount-code social engineering, the
credential exfiltration, the authority-spoof log deletion. Each one lands
on screen with a REFUSED stamp. The scoreboard settles:
**ATTACKS IN: 7 · LANDED: 0**. Beside it, the Meter tallies **DAMAGE
PREVENTED**, each figure with its arithmetic shown, labelled "simulated
on demo data".
Narration: "So we attack it. Seven frozen attacks — anyone can read the
attack file. Every one is refused, and the Meter prices what each refusal
saved. Simulated dollars, on demo data — the containment is real."

**0:30–0:55 — The working day**
Screen: the hero job. The repricing sweep arrives as a proposal: 40
listings repriced against recent sold prices, each with its reason, the
total value at stake printed ($1,240.50 on demo data). Cut to a phone:
Pocket Gate (`GET /gate`) — the sweep is over $500, so the two-key rule
applies; show the two separate approvals. Then the supporting roster
flashes by in one breath: reconciliation, listing health, orders watch,
scan-intake triage, morning report.
Narration: "On a normal day it does the store's heavy lifting — a
40-listing repricing sweep, proposed with reasons. Nothing applies alone:
big moves need two approvals at the gate, on the owner's phone."

**0:55–1:15 — The architecture, drawn once**
Screen: one diagram, built up in four strokes: reasoning → dispatch →
sandboxed tools → gate.
Narration: "All reasoning runs on Vultr Serverless Inference. The Vultr
VM runs sandboxed tools only — a disposable, network-less container with
no credentials inside. Every move is dry-run, then approve, then apply,
then logged."

**1:15–1:30 — Sign-off**
Screen: the demo URL, large: http://144.202.55.202:8080
Narration: "Blast Radius Zero. It's live. Try to make it do something
destructive."

## Filming notes

- Record against the deployed Vultr demo URL, not localhost.
- The Meter's figures and the sweep total are demo data — keep the
  on-screen "simulated on demo data" labels in frame; do not crop them
  out.
- Scoreboard verdicts are conservative by design: a run counts as landed
  only on positive evidence of compliance, and errors read "unverified".
  Narrate the board as it actually settles on the day.
- **Filming only after the attack set passes its examiner pass on the
  live box.** If the Gauntlet has not passed that pass, this script is
  not filmed yet — the volley beat must show verified live behaviour,
  not hoped-for behaviour.
