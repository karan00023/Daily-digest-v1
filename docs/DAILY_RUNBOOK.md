# The Kapoor Daily — daily research and publishing runbook

This is the procedure the morning session follows, whether a person or a scheduled Claude
session runs it. The research step needs an agent with web search; everything after it is
deterministic code (`python -m kapoor_daily.build`).

Target: edition delivered by **07:00 America/New_York**, every day including weekends.
Start research by **06:00 ET**. A full run takes about 30–45 minutes.

---

## 0. Setup (each run)

```bash
cd Daily-digest-v1
pip install -q -r requirements.txt
python -m pytest -q          # must pass before anything is published
DATE=$(TZ=America/New_York date +%F)
```

Read `config/profile.yaml` (reader, holdings, land criteria), `config/preferences.yaml`
(feedback-driven boosts and mutes) and the previous edition's `content.yaml`, so you don't repeat it.

## 1. Research (agent, web search)

Run searches **in parallel batches**. Prefer the last 24 hours, widen to 48–72 hours when needed.
Record each article's publication date separately from the date of the event it describes.

| Desk | Minimum queries |
|---|---|
| A. Morning Brief | top US news today · Fed / rates / inflation / jobs · geopolitics affecting oil or markets · US–India |
| Markets | index closes (S&P, Nasdaq, Dow) · 10-yr yield · gold · WTI · bitcoin · Freddie Mac PMMS (Thursdays) |
| B. Local | Jersey City · Hoboken / Hudson County · PATH / NJ Transit / Gateway · NYC government & MTA · JC council/zoning/tax |
| C. Real estate | land listings in the configured markets (≥4,000 sq ft, ≤$250K) · mortgage rates · NJ/NYC housing |
| D. Portfolio | one query per holding with news in the last 48h (`"<TICKER> stock" + today's date`) · earnings calendar for the next 10 days · re-verify SPCX and IDEXQ weekly |
| E. Research | screen 3–6 candidates in AI/semis/cloud/energy/defense/cyber/ETFs, then keep at most 3 with verifiable metrics |
| F. AI & tech | Anthropic / OpenAI / Google / Microsoft AI · BigQuery / Databricks / Snowflake / AWS / Azure data · MCP & agents |
| G. India | RBI / rupee / economy · Delhi NCR (AQI, metro, infrastructure) · Indian tech & startups · US–India |
| H. Finance & travel | Amex MR transfer bonuses · Amex Platinum offers · NYC–DEL fares · tax changes |
| I. Lifestyle | NBA (Knicks/Nets) · India cricket · major Hollywood & Bollywood releases · NYC/NJ events · space & science |

**Verification rules (from the master prompt, enforced by `validate.py`):**

1. Every substantive item has at least one clickable source. A high-impact claim needs a tier 1–2 source
   (`config/sources.yaml`), or it is labelled *single source*.
2. Never invent news, listings, prices, targets, ratings or quotes. If a value can't be verified, write `unavailable`.
3. Prices are latest reported closes or snapshots with an `as_of`, never "live".
4. Separate fact, analyst opinion and our inference (`inference:` / `labels:` fields).
5. Items older than 72 hours need `context: true` or must be dropped.
6. Don't repeat yesterday's stories unless they materially changed (set `update: true`).
7. Real-estate *matches* need a verified address, URL, price and lot size, and must meet every criterion.
   Everything else is a near miss or is left out. If nothing is new, say so.
8. The Research Desk gets **at most 3 ideas**, uses only the five allowed stances, and contains no position
   sizing while the reader's risk profile is unknown.
9. Anthropic coverage carries the author disclosure.
10. Note any blocked data (feeds, images) in `edition.data_notes`.

Score each candidate story 0–10 on `personal, impact, magnitude, timeliness, actionability`.
The build weights them 35/25/20/10/10, cuts anything under 4.0, and features 7.0+.

## 2. Write `editions/$DATE/content.yaml`

Copy the structure of the most recent edition (the schema is the 2026-10-27 edition plus
`docs/CONTENT_SCHEMA.md`). Set `edition.number` to the previous number + 1 and `researched_at` to now.
Sunday editions add a **Week Ahead** to `action_board.upcoming` and may run up to 12 print pages.

## 3. Build and QA

```bash
python -m kapoor_daily.build --date $DATE      # links come from config/profile.yaml → delivery
```

* Exit **0**: all outputs are in `archive/YYYY-MM/`.
* Exit **1**: content failed validation. Read `*_FAILURE.md`, fix the content (re-research if it's stale), rebuild.
* Exit **2**: print QA failed (clipping, missing story, wrong page size, stranded section head). Shorten or
  fix the content and rebuild.
* After two failed fixes, **stop and send the failure notice** (step 5b). Never deliver a broken edition.

## 4. Publish

1. Commit `editions/$DATE/` and `archive/YYYY-MM/Kapoor_Daily_$DATE*` and push to `delivery.archive_branch`
   (`git push -u origin claude/kapoor-daily-v1`).
2. Update the standing web edition at `delivery.web_edition`: Artifact `read` that URL first, then publish
   `archive/YYYY-MM/Kapoor_Daily_$DATE.artifact.html` with `url` set to it, and pass the three PDFs in `files`
   under their own file names. Never create a second artifact.

## 5. Deliver

a. **Success**: if the Microsoft 365 `outlook_send_mail` tool is available *and* works, send the contents of
   `archive/YYYY-MM/Kapoor_Daily_${DATE}_email.html` as the body (`bodyType: html`) to `delivery.email_to`, with the
   subject `The Kapoor Daily — <Weekday, D Month YYYY>`. As of 27 Oct 2026 the tenant has **not** granted `Mail.Send`
   (403 FORBIDDEN), so expect this to fail. A failed email does not fail the run: note it in the summary. The
   standing web edition and the push notification are the delivery channel.
b. **Failure**: don't republish the web edition. Send the failure notice by email if mail works, and put the top
   errors in the run summary, which the push notification surfaces. Never deliver stale content as today's.

## 6. Learn

If the reader replied to yesterday's email or gave feedback, record it in `config/preferences.yaml`
(`feedback_log`, plus boost/mute/deep-dive entries). Never change holdings or risk settings without
an explicit instruction from the reader.
