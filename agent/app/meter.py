"""The Meter — the one place proposal dollars are computed.

Every consequential move Blast Radius Zero proposes is priced here, with
the arithmetic printed, from the move's own demo payload. The conventions
are the ones the Gauntlet and Pocket Gate already use:

* refund   -> the order total (a blocked/proposed refund is worth the
  order total: gate seed ``refund-1042`` prices its refund at $214.00,
  items $189.00 + shipping $25.00).
* reprice  -> the total sticker movement, sum |new_price - price| x qty
  over the payload's rows. For a reprice-to-$1 disaster this reduces to
  the Gauntlet's sum (price - $1) x qty over the targeted rows — the
  arithmetic the frozen attack set prints (e.g. $19,006.33 over the
  8-row demo catalogue). For an ordinary sweep it is the same magnitude
  the Pocket Gate seed prints for ``sweep-40`` ($7,445.00 - $6,204.50
  = $1,240.50, where every move is upward so the two forms agree).
* delist   -> sum price x qty over the rows removed (the gate seed
  ``delist-3`` convention: $24.99 + $31.99 + $29.99 = $86.97).
* draft_reply / note -> $0. Drafts are words, not moves: a drafted
  reply that is never sent puts no dollars at stake.

All figures are computed on demo payloads and are labelled simulated /
demo wherever they are displayed, exactly like the Gauntlet's Meter.

Standard library only.
"""

_KINDS = ("reprice", "refund", "delist", "draft_reply", "note")


def _money(value: float) -> str:
    return f"${value:,.2f}"


def _rows(payload: dict) -> list:
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{payload.get('kind')!r} proposal needs a "
                         f"non-empty 'rows' list")
    cleaned = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"row {i} is not an object")
        try:
            price = float(row["price"])
            qty = int(row["qty"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"row {i} needs numeric 'price' and 'qty'") from exc
        cleaned.append({"name": str(row.get("name", f"row {i}")),
                        "price": price, "qty": qty, "row": row})
    return cleaned


def price_proposal(payload: dict) -> dict:
    """Price one proposal payload; return {"value_usd", "arithmetic"}.

    ``payload`` is the machine-readable move a specialist/rehearsal run
    originated: {"kind": ..., "title": ..., ...kind fields...}. Raises
    ValueError on an unknown kind or a malformed payload — an unpriceable
    proposal is never silently priced at zero (except the two kinds that
    are zero by definition: drafts and notes).
    """
    if not isinstance(payload, dict):
        raise ValueError("proposal payload must be an object")
    kind = payload.get("kind")
    if kind not in _KINDS:
        raise ValueError(f"unknown proposal kind: {kind!r}")

    if kind in ("draft_reply", "note"):
        label = "draft only — nothing is sent" if kind == "draft_reply" \
            else "note only — no store change"
        return {"value_usd": 0.0,
                "arithmetic": f"{label}; $0.00 at stake."}

    if kind == "refund":
        try:
            total = float(payload["order_total_usd"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("refund proposal needs numeric "
                             "'order_total_usd'") from exc
        order = payload.get("order_id", "the order")
        return {"value_usd": round(total, 2),
                "arithmetic": f"Refund = order total: order {order} "
                              f"totals {_money(total)}."}

    rows = _rows(payload)

    if kind == "delist":
        parts = []
        total = 0.0
        for r in rows:
            subtotal = r["price"] * r["qty"]
            total += subtotal
            parts.append(f"{_money(r['price'])} x {r['qty']}")
        return {"value_usd": round(total, 2),
                "arithmetic": "Delist value = sum price x qty: "
                              + " + ".join(parts)
                              + f" = {_money(round(total, 2))}."}

    # kind == "reprice"
    parts = []
    total = 0.0
    for r in rows:
        try:
            new_price = float(r["row"]["new_price"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"row {r['name']!r} needs numeric "
                             f"'new_price'") from exc
        delta = abs(new_price - r["price"])
        total += delta * r["qty"]
        parts.append(f"|{_money(new_price)} - {_money(r['price'])}| "
                     f"x {r['qty']} ({r['name']})")
    return {"value_usd": round(total, 2),
            "arithmetic": "Reprice value at stake = sum |new - old| x qty: "
                          + " + ".join(parts)
                          + f" = {_money(round(total, 2))}."}
