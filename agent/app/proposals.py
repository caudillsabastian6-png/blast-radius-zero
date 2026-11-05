"""Proposal plumbing shared by Night Shift and Rewind.

A specialist (or rehearsal) run ends with a free-text report. When the
run wants to originate a store move, its report must end with a fenced
JSON block:

    ```json
    {"proposals": [
      {"kind": "reprice", "title": "...", "detail": "...",
       "rows": [{"name": "...", "price": 499.99, "qty": 10,
                 "new_price": 549.99}]},
      {"kind": "refund", "title": "...", "detail": "...",
       "order_id": "DEMO-1042", "order_total_usd": 214.0},
      {"kind": "draft_reply", "title": "...", "detail": "..."}
    ]}
    ```

``extract_proposals`` finds that block and returns the payload dicts,
unpriced and unjudged — pricing is the Meter's job (app/meter.py) and
judging (budgets, rehearsal invariants) is the runner's job. Extraction
is deliberately lenient about the surrounding prose and strict about
the payloads: anything that is not a JSON object with a ``proposals``
list of objects carrying a string ``kind`` and ``title`` yields no
proposals at all. A run that produces no block has simply proposed
nothing; that is a normal outcome, recorded as such — never an error
worth inventing proposals over.

Standard library only.
"""

import json
import re

_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)

# The instruction block runners append to a specialist/rehearsal task so
# the model's final report can carry machine-readable proposals. The
# wording mirrors extract_proposals' contract exactly.
PROPOSAL_BLOCK_INSTRUCTIONS = """
When your work warrants a store move, end your report with a fenced JSON
block listing every move you propose, exactly in this shape (demo data
only; propose, never apply):

```json
{"proposals": [{"kind": "reprice", "title": "short title", "detail": "what and why", "rows": [{"name": "Card name", "price": 499.99, "qty": 10, "new_price": 549.99}]}, {"kind": "refund", "title": "short title", "detail": "what and why", "order_id": "DEMO-1042", "order_total_usd": 214.0}, {"kind": "delist", "title": "short title", "detail": "what and why", "rows": [{"name": "Card name", "price": 24.99, "qty": 1}]}, {"kind": "draft_reply", "title": "short title", "detail": "the draft's gist"}]}
```

Kinds: "reprice" (rows carry price, qty, new_price), "refund"
(order_id, order_total_usd), "delist" (rows carry price, qty),
"draft_reply" and "note" (no dollars at stake). If no move is warranted,
end with {"proposals": []}. Do not invent rows, prices or orders that
are not in the files you were given."""


def _candidates(text: str):
    """Yield JSON-object strings worth trying, most-structured first."""
    for match in _FENCE.findall(text):
        yield match
    start = text.find('{"proposals"')
    if start >= 0:
        yield text[start:]


def extract_proposals(answer) -> list:
    """Return the proposal payloads from a run's final answer (or [])."""
    if not isinstance(answer, str) or not answer.strip():
        return []
    for candidate in _candidates(answer):
        try:
            parsed = json.loads(candidate)
        except (ValueError, json.JSONDecodeError):
            continue
        if not isinstance(parsed, dict):
            continue
        proposals = parsed.get("proposals")
        if not isinstance(proposals, list):
            continue
        cleaned = []
        for item in proposals:
            if not isinstance(item, dict):
                return []
            if not isinstance(item.get("kind"), str) \
                    or not isinstance(item.get("title"), str):
                return []
            cleaned.append(item)
        return cleaned
    return []
