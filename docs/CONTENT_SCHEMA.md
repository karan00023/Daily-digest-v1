# content.yaml schema

One file per day at `editions/YYYY-MM-DD/content.yaml` (JSON also accepted). The sample edition
`editions/2026-10-27/content.yaml` is the reference implementation of every field.

```yaml
edition:
  date: 2026-10-27              # must match the folder
  number: 1
  researched_at: "2026-10-27T05:30:00-04:00"   # build refuses content more than 20h old
  research_window: "…"
  disclosure: "…"               # author disclosure (Claude / Anthropic)
  data_notes: ["…"]             # blocked feeds, single-source figures, etc.

lead: <story id>

market_snapshot:                # each needs as_of + src; never "live"
  - {label, value, change, as_of, src}

graphics:                       # optional, verified numbers only
  fed_odds: {title, as_of, bars: [{label, value}], source: {name, url}}

stories:                        # sections: brief local realestate tech india finance lifestyle
  - id, section, kind (news|analysis|opinion|opportunity|context)
    headline, dek, summary       # summary = what happened, 2–3 sentences
    why                          # why it matters
    me                           # Why This Matters to Me (personal/financial implications)
    use                          # optional: How I Could Use This (tech)
    linkedin                     # optional: post angle
    inference                    # optional: our read / disclosure, rendered as opinion
    event_date, context: bool, update: bool, tickers: [..], qr: bool
    sources: [{name, url, published}]          # published: YYYY-MM-DD preferred
    scores: {personal, impact, magnitude, timeliness, actionability}   # 0–10

world_in_brief: [{text, src, published}]

portfolio:
  verification: [{ticker, status, finding, action, sources}]     # ambiguous/distressed tickers
  developments: [{ticker, also, headline, what, signal (bullish|bearish|neutral),
                  horizon, materiality, consider, labels: {fact, opinion, inference}, sources}]
  watchlist: [{ticker, last, as_of, note, src}]                  # configured holdings only
  exposure_note: "…"

realestate:
  criteria_text, no_match_note, market_reality
  matches: [{address, url, price, lot_sqft, taxes, zoning, drive, why, risks}]   # verified + meets criteria
  near_misses: [same fields]     # price_per_sqft and the failing criteria are computed by the build
  sources: [...]

research:
  preface
  ideas: (max 3) [{name, ticker, business, price, price_time, thesis, metrics, catalysts, bear,
                   alternatives, valuation, horizon, invalidation, fit,
                   stance (Research Further|Potential Buy|Hold|Trim|Avoid), conviction, sources}]

action_board:
  three_things: [3 strings]
  two_opportunities: [{title, detail} × 2]
  one_action: "…"
  upcoming: [{date, event}]
```
