"""Source validation, freshness and factual-discipline checks.

Errors block publication (a failure report is produced instead). Warnings are
printed in the edition's "Sources & data notes" so the reader sees them.
"""

import datetime as dt
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

SECTIONS = {"brief", "local", "realestate", "portfolio", "research", "tech", "india", "finance", "lifestyle"}
KINDS = {"news", "analysis", "opinion", "opportunity", "context"}
SCORE_KEYS = ("personal", "impact", "magnitude", "timeliness", "actionability")
STANCES = {"Research Further", "Potential Buy", "Hold", "Trim", "Avoid"}
SIGNALS = {"bullish", "bearish", "neutral"}
UNAVAILABLE = re.compile(r"^(unavailable|not yet priced|n/a|—|see story)", re.I)
NUMERIC = re.compile(r"[\d]")
SIZING = re.compile(r"\b(allocate|allocation of|position size|put \d+%|buy \d+ shares)\b", re.I)


@dataclass
class Report:
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    def error(self, where, msg):
        self.errors.append(f"{where}: {msg}")

    def warn(self, where, msg):
        self.warnings.append(f"{where}: {msg}")

    @property
    def ok(self):
        return not self.errors


def domain_of(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def source_tier(url: str, registry: dict) -> int | None:
    host = domain_of(url)
    for tier, key in ((1, "tier1"), (2, "tier2"), (3, "tier3")):
        for d in registry.get(key, []):
            if host == d or host.endswith("." + d):
                return tier
    return None


def parse_published(value) -> tuple[dt.date | None, str]:
    """Return (date, precision). Precision is 'day', 'month', 'year' or 'unknown'."""
    if isinstance(value, dt.datetime):
        return value.date(), "day"
    if isinstance(value, dt.date):
        return value, "day"
    s = str(value or "").strip()
    for fmt, prec in (("%Y-%m-%dT%H:%M:%S%z", "day"), ("%Y-%m-%d", "day"), ("%Y-%m", "month"), ("%Y", "year")):
        try:
            return dt.datetime.strptime(s, fmt).date(), prec
        except ValueError:
            continue
    return None, "unknown"


def _check_sources(where, sources, registry, rep, required=True):
    if not sources:
        if required:
            rep.error(where, "no sources — every substantive item needs a clickable source")
        return []
    tiers = []
    for s in sources:
        url = (s or {}).get("url", "")
        if not url.startswith(("http://", "https://")):
            rep.error(where, f"source without a valid URL: {s!r}")
            continue
        if not s.get("name"):
            rep.warn(where, f"source missing a display name: {url}")
        t = source_tier(url, registry)
        if t is None:
            rep.warn(where, f"unregistered source domain {domain_of(url)} — add it to config/sources.yaml with a tier")
        tiers.append(t)
    return tiers


def validate(content: dict, cfg: dict, build_time: dt.datetime | None = None) -> Report:
    rep = Report()
    reg = cfg["sources"]
    ed = content.get("edition", {})
    max_age = dt.timedelta(hours=cfg["freshness"]["max_hours"])

    # Edition-level staleness: refuse to publish content researched too long ago.
    try:
        ed_date = dt.date.fromisoformat(str(ed["date"]))
    except (KeyError, ValueError):
        rep.error("edition", "missing or invalid edition.date")
        return rep
    researched = ed.get("researched_at")
    if not researched:
        rep.error("edition", "missing researched_at timestamp")
    elif build_time is not None:
        ts = researched if isinstance(researched, dt.datetime) else dt.datetime.fromisoformat(str(researched))
        age = build_time - ts
        if age > dt.timedelta(hours=20):
            rep.error("edition", f"STALE: research is {age} old; re-run research before publishing")
        if ts.date() > ed_date or ed_date - ts.date() > dt.timedelta(days=1):
            rep.error("edition", f"researched_at {ts.isoformat()} does not belong to edition {ed_date}")

    # Stories
    ids = set()
    for st in content["stories"]:
        sid = st.get("id", "?")
        where = f"story[{sid}]"
        if sid in ids:
            rep.error(where, "duplicate id")
        ids.add(sid)
        for k in ("headline", "summary", "section"):
            if not st.get(k):
                rep.error(where, f"missing {k}")
        if st.get("section") not in SECTIONS:
            rep.error(where, f"unknown section {st.get('section')!r}")
        if st.get("kind", "news") not in KINDS:
            rep.error(where, f"unknown kind {st.get('kind')!r}")
        scores = st.get("scores", {})
        for k in SCORE_KEYS:
            v = scores.get(k)
            if not isinstance(v, (int, float)) or not 0 <= v <= 10:
                rep.error(where, f"score {k} must be 0–10 (got {v!r})")
        tiers = _check_sources(where, st.get("sources"), reg, rep)
        if tiers and all(t == 3 or t is None for t in tiers) and scores.get("magnitude", 0) >= 8:
            rep.warn(where, "high-impact claim rests only on tier-3/unregistered sources — corroborate")

        # Freshness: newest source must be within the window unless marked context.
        newest, precise = None, False
        for s in st.get("sources") or []:
            d, prec = parse_published(s.get("published"))
            if d and (newest is None or d > newest):
                newest, precise = d, prec == "day"
        if newest is None:
            rep.warn(where, "no parseable publication dates on sources")
        elif not st.get("context"):
            age = dt.datetime.combine(ed_date, dt.time()) - dt.datetime.combine(newest, dt.time())
            if precise and age > max_age:
                rep.error(where, f"newest source is {age.days} days old; mark context: true or drop it")
            elif not precise:
                rep.warn(where, "source dates only month-precise; freshness could not be fully verified")

    lead = content.get("lead")
    if lead and lead not in ids:
        rep.error("lead", f"lead story {lead!r} not found")

    # Market snapshot: every number needs an as-of and a source. Never present as live.
    for m in content["market_snapshot"]:
        where = f"market[{m.get('label')}]"
        if not m.get("as_of"):
            rep.error(where, "missing as_of — prices must never appear without a timestamp")
        if not m.get("src"):
            rep.error(where, "missing source")
        if "live" in str(m.get("as_of", "")).lower():
            rep.error(where, "do not label prices 'live' — the pipeline has no real-time feed")

    # Portfolio: never invent holdings; every price needs a timestamp.
    pf = content["portfolio"]
    holdings = {h["ticker"] for h in cfg["portfolio"]["holdings"]}
    for dev in pf.get("developments", []):
        where = f"portfolio[{dev.get('ticker')}]"
        for t in [dev.get("ticker")] + dev.get("also", []):
            if t not in holdings:
                rep.error(where, f"{t} is not a configured holding — holdings change only on reader instruction")
        if dev.get("signal") not in SIGNALS:
            rep.error(where, "signal must be bullish/bearish/neutral")
        for k in ("what", "horizon", "materiality", "consider"):
            if not dev.get(k):
                rep.error(where, f"missing {k}")
        _check_sources(where, dev.get("sources"), reg, rep)
    seen = set()
    for w in pf.get("watchlist", []):
        t = w.get("ticker")
        where = f"watchlist[{t}]"
        if t not in holdings:
            rep.error(where, "not a configured holding")
        seen.add(t)
        last = str(w.get("last", ""))
        if NUMERIC.search(last) and not UNAVAILABLE.match(last) and not w.get("as_of"):
            rep.error(where, "price without an as-of date")
    for t in sorted(holdings - seen):
        rep.warn("watchlist", f"{t} missing from the watchlist table")
    for v in pf.get("verification", []):
        _check_sources(f"verification[{v.get('ticker')}]", v.get("sources"), reg, rep)
    flagged = {h["ticker"] for h in cfg["portfolio"]["holdings"] if h.get("flag")}
    verified = {v.get("ticker") for v in pf.get("verification", [])}
    for t in sorted(flagged - verified):
        rep.warn("portfolio", f"{t} is flagged ambiguous/distressed but has no verification note today")

    # Research desk
    ideas = content["research"].get("ideas", [])
    if len(ideas) > 3:
        rep.error("research", "no more than 3 ideas per edition")
    reader = cfg["reader"]
    personal_unknown = any(reader.get(k) is None for k in ("risk_tolerance", "time_horizon", "liquidity_needs", "tax_situation"))
    for i in ideas:
        where = f"research[{i.get('ticker')}]"
        if i.get("stance") not in STANCES:
            rep.error(where, f"stance must be one of {sorted(STANCES)}")
        for k in ("thesis", "bear", "invalidation", "fit", "conviction", "horizon"):
            if not i.get(k):
                rep.error(where, f"missing {k}")
        price = str(i.get("price", ""))
        if not price:
            rep.error(where, "price must be given with a timestamp or marked unavailable")
        elif not UNAVAILABLE.match(price) and not i.get("price_time"):
            rep.error(where, "price given without price_time")
        if personal_unknown and SIZING.search(" ".join(str(v) for v in i.values())):
            rep.error(where, "position sizing/allocation language while reader risk profile is unknown")
        _check_sources(where, i.get("sources"), reg, rep)

    # Real estate: only verified listings that meet every criterion are "matches".
    re_cfg = cfg["real_estate"]
    for m in content["realestate"].get("matches", []):
        where = f"listing[{m.get('address')}]"
        for k in re_cfg["require_verified"]:
            if not m.get(k):
                rep.error(where, f"match missing verified {k}")
        if (m.get("lot_sqft") or 0) < re_cfg["min_lot_sqft"] or (m.get("price") or 1e12) > re_cfg["max_price_usd"]:
            rep.error(where, "does not meet size/price criteria — list it as a near miss instead")
    _check_sources("realestate", content["realestate"].get("sources"), reg, rep, required=False)

    # Action board shape
    ab = content["action_board"]
    if len(ab.get("three_things", [])) != 3:
        rep.error("action_board", "needs exactly 3 'Things Worth Knowing'")
    if len(ab.get("two_opportunities", [])) != 2:
        rep.error("action_board", "needs exactly 2 opportunities")
    if not ab.get("one_action"):
        rep.error("action_board", "needs 1 action")

    for w in content["world_in_brief"]:
        if not str(w.get("src", "")).startswith("http"):
            rep.error("world_in_brief", f"item without source: {w.get('text')!r}")

    return rep
