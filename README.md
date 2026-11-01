# Blast Radius Zero

A store-ops agent for Card Cauldron TCG that does real shop work end-to-end — and cannot hurt anything while it does it.

Built for the **Vultr: Agent Rush Hackathon** (LabLab), Nov 3–8, 2026. Entrant: Sabastian Edward Caudill (LabLab: CardCauldronTCG). Submission due Nov 8, 2026, 6:00 PM EST.

## The fence (every job, every run)
1. **Read** the store's real state — eBay listings, the Card Value Tracker, the scan pool.
2. **Check** it against the rules and market evidence; propose changes with reasons.
3. **Dry run first** — nothing live moves until the change set is approved.
4. **Apply + log + undo** — every applied move is recorded and reversible.

## Jobs
1. **Repricing sweep** — every card and every listing checked against current comps; graded slabs priced by PSA values, not eBay sold.
2. **Reconciliation** — tracker vs. eBay drift: sold-but-listed, duplicates, quantity mismatches, orphans both ways.
3. **Listing health** — photo URLs load-tested (not just API-read), Best Offer state verified, title/category problems.
4. **Orders & trouble watch** — unshipped orders, buyer claims, negative feedback with a recovery draft.
5. **Intake triage** — pool submissions into labelled identity drafts + approval packets.
6. **The morning list** — one report: what ran, what changed, what's waiting for the owner.

Proving ground: the current store (buckeyebinder). Graduation job, post-hackathon: run the migration to the owner's own eBay account once the LLC/EIN/new account exist.

## How it runs
Hosted on a Vultr cloud server claimed at kickoff (Nov 3, 15:00 UTC) with the event's $200 gift credit. Reaches the shop through the same APIs the shop already uses (eBay Sell APIs; the Card Tracker). Demo path runs on sandbox copies of store data.

## Proof
Every run writes its own evidence: the dry-run report, the approval record, and the applied-change log with before/after values. This repo's commit history plus those run logs are the build record.

## Fences inherited from the shop
Never relist a sold card. Never invent a price, a comp, or a verdict. No spend beyond the event credit without the owner's tap. Private shop data stays home — demos use sandbox copies.
