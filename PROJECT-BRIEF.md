# Blast Radius Zero — Vultr: Agent Rush Hackathon project brief

**Owner-ruled scope, Oct 31, 2026 (~11:46 PM ET).** Entrant: Sabastian Edward Caudill (LabLab: CardCauldronTCG). Event: online build Nov 3–8, 2026; **submission due Nov 8, 6:00 PM EST** on LabLab. Kickoff Nov 3, 15:00 UTC (11:00 AM EST): create the Vultr account on caudillsabastian6@gmail.com and claim the **$200 gift code** (Billing → Gift Code → Apply). Prize pool $14,000; entrant keeps IP; solo OK; online-only (no Salt Lake City travel).

**Repo (created Oct 31, 2026, owner-tapped):** https://github.com/caudillsabastian6-png/blast-radius-zero — PRIVATE, seeded with the README + .gitignore (commit 4b74465). Local working copy: `blast-radius-zero/` beside this brief. Teams for this event: **1–6** (currently solo).

## The idea in one line
A store-ops agent for Card Cauldron TCG that does real shop work end-to-end — and cannot hurt anything while it does it.

## The fence (applies to every job)
1. **Read** the store's real state (eBay listings, Card Value Tracker, scan pool).
2. **Check** it against the rules and market evidence; produce proposed changes with reasons.
3. **Dry run first** — nothing live moves until the change set is approved.
4. **Apply + log + undo** — every applied move is recorded and reversible.

## Job slate (owner: "Let's give it multiple jobs")
1. **Repricing sweep** (owner's pick for job #1) — run through every card and every eBay listing, check each against current comps; graded slabs priced by PSA values, not eBay sold. Propose new prices with reasons.
2. **Reconciliation** — tracker ↔ eBay drift: sold cards still listed, duplicate listings, quantity mismatches, listings with no tracker record, tracker records with no listing.
3. **Listing health** — photos that no longer render (verify the hosted image actually loads, not just the API field), Best Offer state read back and confirmed, title/category problems.
4. **Orders & trouble watch** — unshipped orders before they become cases, buyer claims/INRs, negative feedback with a recovery draft prepared.
5. **Intake triage** — pool submissions turned into labelled identity drafts + approval packets; nothing enters the library without the owner's approval.
6. **The morning list** — one report tying it together: what the agent did, what it proposes, what needs the owner's eyes.

All six jobs run on the one engine (read → check → dry-run → approve → apply/log/undo); the multi-job scope is one machine with several duties, not six separate builds.

## Build reality
- Meta hackathon submission occupies Nov 3–4; Vultr building runs Nov 5–8 in earnest.
- Runs on Vultr cloud (the $200 credit); sandbox copies of store data for the demo path — the fence is the product, the demo shows it working on real-shaped work.
- Submission: LabLab project page + demo by Nov 8, 6:00 PM EST.

## After the hackathon — the graduation job (owner-confirmed Oct 31, ~11:49 PM ET)
The agent's proving ground is the CURRENT store (buckeyebinder, in Chris Golliver's name): jobs 1–6 run over it first, where mistakes are recoverable. Once the hackathons are filed and the agent is built and proven, the sequence is:
1. **LLC filed** (Card Cauldron TCG LLC, Ohio, $99 — owner's word) → **EIN**.
2. **New eBay account** in Sabastian's own name under the business.
3. **The agent runs the migration** — listings re-created, repriced, and reconciled over to the new account under the fence, gradually (a new account's selling limits ramp with history; the old store keeps selling while the new one grows into its limits).
Owner's words: "it runs over Chris's store now and then once everything's done and we build the thing it can then migrate over to mine."

## Standing fences inherited from the shop
- Never relist a sold card. Never invent a price, a comp, or a verdict. Spending beyond the $200 credit needs the owner's tap. Private shop data stays home — demo data is sandbox copies.
