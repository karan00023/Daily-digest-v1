"""Relevance scoring, reader preferences and deduplication."""

import re

STOP = set("a an the and or of to in on for with as at by from is are be its it this that after over into says new".split())


def tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9$%.]+", text.lower()) if w not in STOP and len(w) > 1}


def jaccard(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    return len(ta & tb) / len(ta | tb) if ta and tb else 0.0


def score(story: dict, weights: dict) -> float:
    s = story.get("scores", {})
    return round(sum(weights[k] * s.get(k, 0) for k in weights), 2)


def _text(story):
    return " ".join(str(story.get(k, "")) for k in ("headline", "dek", "summary"))


def apply_preferences(stories, prefs, log):
    mutes = [m["topic"].lower() for m in prefs.get("mute_topics") or []]
    boosts = [b["topic"].lower() for b in prefs.get("boost_topics") or []]
    kept = []
    for st in stories:
        text = _text(st).lower()
        if any(m in text for m in mutes):
            log.append(f"Dropped '{st['headline']}' — matches a muted topic")
            continue
        if any(b in text for b in boosts):
            st.setdefault("scores", {})["personal"] = min(10, st["scores"].get("personal", 0) + 1)
        kept.append(st)
    return kept


def dedupe(stories, previous_editions, log, threshold=0.6):
    """Remove within-edition duplicates and repeats of recent editions.

    A repeat survives only when flagged `update: true` (the story materially changed).
    """
    prior = [s for ed in previous_editions for s in ed.get("stories", [])]
    out = []
    for st in stories:
        dup = next((o for o in out if jaccard(o["headline"], st["headline"]) >= threshold
                    or (shared_url(o, st) and jaccard(_text(o), _text(st)) >= 0.35)), None)
        if dup:
            log.append(f"Merged duplicate '{st['headline']}' into '{dup['headline']}'")
            continue
        old = next((p for p in prior if p.get("id") == st["id"] or jaccard(p["headline"], st["headline"]) >= threshold), None)
        if old and not st.get("update"):
            log.append(f"Skipped repeat of a recent edition: '{st['headline']}'")
            continue
        out.append(st)
    return out


def shared_url(a, b):
    ua = {s.get("url") for s in a.get("sources") or []}
    ub = {s.get("url") for s in b.get("sources") or []}
    return bool(ua & ub)


def rank(content: dict, cfg: dict, previous_editions: list, log: list) -> dict:
    """Return {section_id: [stories...]} ordered by weighted relevance, capped per section."""
    weights = cfg["relevance_weights"]
    stories = apply_preferences(list(content["stories"]), cfg.get("preferences", {}), log)
    stories = dedupe(stories, previous_editions, log)
    for st in stories:
        st["score"] = score(st, weights)
        st["featured"] = st["score"] >= cfg["feature_threshold"]
    by_section = {}
    caps = {s["id"]: s["max"] for s in cfg["sections"]}
    for st in sorted(stories, key=lambda s: -s["score"]):
        if st["score"] < cfg["drop_threshold"] and st["id"] != content.get("lead"):
            log.append(f"Cut low-relevance item '{st['headline']}' (score {st['score']})")
            continue
        sec = by_section.setdefault(st["section"], [])
        if len(sec) >= caps.get(st["section"], 5):
            log.append(f"Section cap reached; held '{st['headline']}'")
            continue
        sec.append(st)
    return by_section
