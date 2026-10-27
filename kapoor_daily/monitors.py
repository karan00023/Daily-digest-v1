"""Portfolio and real-estate monitoring logic.

Both monitors work on what the research step found; they never fabricate data.
Missing values render as "unavailable" and are counted in the data notes.
"""


def portfolio_table(content: dict, cfg: dict) -> list[dict]:
    """One row per configured holding (never double-counted across accounts)."""
    pf = content.get("portfolio", {})
    watch = {w["ticker"]: w for w in pf.get("watchlist", [])}
    devs = {}
    for d in pf.get("developments", []):
        for t in [d["ticker"]] + d.get("also", []):
            devs.setdefault(t, d)
    checks = {v["ticker"]: v for v in pf.get("verification", [])}
    rows = []
    for h in cfg["portfolio"]["holdings"]:
        t = h["ticker"]
        w = watch.get(t, {})
        d = devs.get(t)
        rows.append({
            "ticker": t,
            "name": h["expected"],
            "type": h["type"],
            "flag": h.get("flag"),
            "last": w.get("last") or "unavailable",
            "as_of": w.get("as_of", ""),
            "note": w.get("note", ""),
            "src": w.get("src", ""),
            "signal": d["signal"] if d and d["ticker"] == t else None,
            "has_story": bool(d),
            "verification": checks.get(t, {}).get("status"),
        })
    return rows


def unavailable_count(rows) -> int:
    return sum(1 for r in rows if str(r["last"]).lower().startswith("unavailable"))


def evaluate_listing(listing: dict, criteria: dict) -> dict:
    """Classify a listing against the land criteria and compute price per sq ft."""
    price, lot = listing.get("price"), listing.get("lot_sqft")
    out = dict(listing)
    if price and lot:
        out["price_per_sqft"] = round(price / lot, 2)
    fails = []
    if lot is None:
        fails.append("lot size unknown")
    elif lot < criteria["min_lot_sqft"]:
        fails.append(f"lot {lot:,} sq ft < {criteria['min_lot_sqft']:,}")
    if price is None:
        fails.append("price unknown")
    elif price > criteria["max_price_usd"]:
        fails.append(f"price ${price:,} > ${criteria['max_price_usd']:,}")
    out["fails"] = fails
    out["is_match"] = not fails
    return out


def real_estate_view(content: dict, cfg: dict) -> dict:
    re_c = dict(content.get("realestate", {}))
    crit = cfg["real_estate"]
    re_c["matches"] = [evaluate_listing(m, crit) for m in re_c.get("matches", [])]
    re_c["near_misses"] = [evaluate_listing(m, crit) for m in re_c.get("near_misses", [])]
    re_c["nyc_reference"] = crit["nyc_reference"]
    return re_c
