# Automation: 7:00 AM Eastern, every day

## What is automated, and what does it need?

| Step | Runs on | Needs | Status |
|---|---|---|---|
| Research (news, markets, listings) | A Claude Code cloud session, started by a **scheduled task** | Web search (built in) | Approved 27 Oct 2026, scheduled daily 06:05 ET |
| Validate → rank → render HTML/email → typeset A4, Bound, A5 booklet PDFs → print QA | Same session: `python -m kapoor_daily.build` | Python 3, Chromium + Playwright (preinstalled) | Built and tested in this repo |
| Archive | Git: `editions/` (content) and `archive/YYYY-MM/` (outputs) | Push access to `karan00023/daily-digest-v1` (GitHub app already connected) | Approved; branch `claude/kapoor-daily-v1` |
| Web edition + PDFs on iPhone | A private claude.ai Artifact updated daily, with the PDFs published alongside it | Your claude.ai login on the phone | Ready |
| Email digest | GitHub Actions `.github/workflows/deliver.yml`, run on every pushed edition. Sends from your own Gmail by SMTP with the A4 PDF attached | Repo secrets `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD` | Built; waiting on the two secrets (only you can create a Google App Password) |
| WhatsApp alert | Same workflow, via the free CallMeBot WhatsApp API | Repo secrets `WHATSAPP_PHONE` and `CALLMEBOT_APIKEY` | Built; optional, waiting on your CallMeBot key |
| Failure reporting | Same session: emails a failure notice instead of the edition | — | Built (`*_FAILURE.md`) |

### Constraints found while building

* **Network policy.** This environment blocks direct market-data APIs (Yahoo, Stooq, FRED, CoinGecko),
  RSS feeds and image hosts. Research therefore goes through the agent's web search, and the edition
  states this in its data notes. To get live quotes and photos, allow those hosts in the environment's network
  settings or add a market-data API key as an environment secret. The pipeline would then show that data with
  timestamps; it never fabricates it.
* **Email sanitizer.** The Outlook connector strips `<style>`, `<span>` and `<img>`, and it cannot attach files.
  The email template is therefore plain semantic HTML that links to the web edition and the A4 PDF.
* **Work mailbox.** The only connected mail connector is your employer's Microsoft 365 tenant, which has read-only
  permissions (no `Mail.Send`). Email therefore goes through GitHub Actions and your own Gmail instead.

## The scheduled task

A Claude Code scheduled task fires at **06:05 ET** daily (`CRON_TZ=America/New_York 5 6 * * *`)
**into the original build session** (session_01RrMUWPVX14PYjroHFcs1ue), not a fresh one.

The first version started a fresh session each morning. Those sessions had no repo push access and no
connectors. On 29 Oct the edition was built and the web page updated, but the git push failed with a 403 and
that day's archive commit was lost. Running in the original session keeps push access and the Microsoft 365 connector.

Manage the task on claude.ai → Code → Scheduled tasks, or ask Claude to pause, retime or delete it.

### Alternative without Claude scheduling: GitHub Actions

`.github/workflows/daily.yml` (not created by default) could run the same runbook with the
Claude Code GitHub Action on a `schedule:` trigger. This needs an `ANTHROPIC_API_KEY` repository
secret, SMTP or Gmail credentials for email, and GitHub Pages (or a release asset) for the PDFs.

## Turning on email and WhatsApp (about 5 minutes, one time)

These steps need your Google account and your phone, so only you can do them.

**Email (Gmail, with the A4 PDF attached)**
1. Turn on 2-Step Verification for karan.kapoor5137@gmail.com if it isn't already on.
2. Go to https://myaccount.google.com/apppasswords, create an app password named "Kapoor Daily", and copy the 16 characters.
3. In GitHub, open karan00023/daily-digest-v1 → Settings → Secrets and variables → Actions → New repository secret. Add:
   * `GMAIL_ADDRESS` = `karan.kapoor5137@gmail.com`
   * `GMAIL_APP_PASSWORD` = the 16 characters, without spaces
4. Test it: Actions → Deliver edition → Run workflow. The latest edition should arrive in your Gmail within a minute.

**WhatsApp (optional)**
1. Save **+34 644 51 95 23** in your phone's contacts. That's CallMeBot, a free and unofficial WhatsApp API service.
2. Send it this WhatsApp message: `I allow callmebot to send me messages`
3. It replies with your API key. Add two more repository secrets:
   * `WHATSAPP_PHONE` = your number with country code, e.g. `+12015551234`
   * `CALLMEBOT_APIKEY` = the key
4. Run the workflow again to test. Each morning you'll get the headline and the web-edition link on WhatsApp.

The Microsoft 365 route remains an option: the morning run still tries it. It starts working only if your IT admin grants the
connector `Mail.Send`.

## Printing from iPhone (AirPrint)

Open the email, tap **A4 print PDF** (or open the web edition and tap *Print: A4*), then
Share → Print. Print at 100% / "Actual size". The PDF is true A4 (210 × 297 mm), uses grayscale-safe
styling, and works offline once opened.

* **Edition A (A4):** duplex long-edge.
* **Edition B (Bound):** duplex long-edge. Pages have a 24 mm inner gutter, the running heads sit on the
  outer edge, and it opens with a cover and contents.
* **A5 booklet:** pages are already imposed 2-up on A4 landscape. Print duplex **short-edge**, stack, fold in half.

## Testing done

* `python -m pytest`: 19 tests covering validation, stale research, the 72-hour rule, invented holdings,
  untimestamped prices, position-sizing guard, dedupe across days, ranking cuts, listing evaluation,
  booklet imposition and missing-edition failure.
* Full build of the 2026-10-27 edition: print QA checks A4 dimensions, embedded fonts, clipped/overflowing
  elements, that every headline is present, and stranded section heads (auto-fixed with a page break).
* Stale-data run: building the same content with `--now` one day later exits 1 with
  `STALE: research is … old` and writes a failure report.
