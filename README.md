# The Kapoor Daily

A personalised morning newspaper for a reader in Jersey City Heights. It covers news, local
intelligence, a property radar, portfolio monitoring, a research desk, AI and data platforms,
India and Delhi, points and travel, and an action board. It ships as an interactive web edition,
an email digest, and typeset A4, bound and A5-booklet PDFs.

```
config/        profile (reader, holdings, land criteria, weights), source tiers, feedback preferences
editions/      one researched content.yaml per day (the editorial record)
kapoor_daily/  validate → rank/dedupe → monitors → render → print/QA → build
templates/     web.html.j2 (responsive, light/dark) · email.html.j2 (Outlook-safe) · print.html.j2 (paged media)
scripts/       pdf.mjs, the Chromium typesetter with a layout probe
assets/fonts/  vendored OFL fonts, embedded in the PDFs
archive/       published outputs per month
docs/          DAILY_RUNBOOK.md · AUTOMATION.md · CONTENT_SCHEMA.md
```

```bash
pip install -r requirements.txt
python -m pytest -q
python -m kapoor_daily.build --date 2026-10-27 --now 2026-10-27T06:30:00-04:00
```

Outputs for each day (`archive/YYYY-MM/`):
`Kapoor_Daily_YYYY-MM-DD.html`, `_A4.pdf`, `_Bound.pdf`, `_A5_Booklet.pdf`, `_email.html`, `_build_report.json`.

Research is done by an agent following `docs/DAILY_RUNBOOK.md`. The code never fetches or invents
facts: it validates what research found (sources, timestamps, freshness, holdings, research-desk rules)
and refuses to publish when something is wrong.
