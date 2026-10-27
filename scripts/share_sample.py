"""Make a shareable sample of an edition: a front-page PNG and a short PDF.

Private material is removed: holdings, points balance, portfolio, property search,
research desk and personal-finance pages.

    python scripts/share_sample.py --date 2026-10-27
"""

import argparse
import copy
import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kapoor_daily import ROOT  # noqa: E402
from kapoor_daily.build import out_paths  # noqa: E402
from kapoor_daily.loader import load_config, load_edition  # noqa: E402
from kapoor_daily.printing import find_group_pages, orphaned_sections, typeset  # noqa: E402
from kapoor_daily.rank import rank  # noqa: E402
from kapoor_daily.render import SECTION_TITLES, build_context, render  # noqa: E402
from kapoor_daily.validate import Report  # noqa: E402

PRIVATE = re.compile(r"\b(your holdings?|your portfolio|your position|MR points|Membership Rewards points|400,?000|400K)\b", re.I)


def scrub(text, tickers):
    """Drop every sentence that mentions a holding or a private figure."""
    if not text:
        return text
    pat = re.compile(r"\b(" + "|".join(map(re.escape, tickers)) + r")\b")
    sentences = re.split(r"(?<=[.!?])\s+", str(text))
    kept = [s for s in sentences if not pat.search(s) and not PRIVATE.search(s)]
    return " ".join(kept)


def sanitize(content, cfg):
    c = copy.deepcopy(content)
    tickers = [h["ticker"] for h in cfg["portfolio"]["holdings"]]
    c["stories"] = [s for s in c["stories"] if s["section"] not in ("finance", "realestate")]
    for st in c["stories"]:
        for k in ("dek", "me", "use", "inference", "why"):
            st[k] = scrub(st.get(k), tickers)
        st.pop("tickers", None)
    c["portfolio"] = {"developments": [], "verification": [], "watchlist": []}
    c["research"] = {"ideas": []}
    c["realestate"] = {}
    c["action_board"]["upcoming"] = [u for u in c["action_board"].get("upcoming", [])
                                     if not re.search(r"Amex|Ocugen|Red Cat|AMD|property tax", u["event"])]
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=dt.date.today().isoformat())
    args = ap.parse_args()
    date = dt.date.fromisoformat(args.date)
    cfg = load_config()
    content = sanitize(load_edition(date), cfg)
    log = []
    ranked = rank(content, cfg, [], log)
    ctx = build_context(content, cfg, ranked, Report(), [])
    ctx.update(digital_only=[], warnings=[], data_notes=[])

    paths = out_paths(date)
    work = paths["work"]
    work.mkdir(parents=True, exist_ok=True)
    html, pdf = work / "share.html", paths["dir"] / f"Kapoor_Daily_{date}_Sample.pdf"
    titles = {k: ctx["print_titles"][k] for k in ("brief", "local", "tech", "india", "lifestyle")}
    pages, force = {"front": 1}, set()
    # Repeat until page numbers settle and no section head is stranded at a page foot.
    for _ in range(5):
        html.write_text(render("print.html.j2", {**ctx, "force_break": force}, variant="a4", share=True,
                               pages=pages, fonts_css=(ROOT / "assets/fonts/fonts.css").as_uri()))
        typeset(html, pdf)
        new = {"front": 1, **find_group_pages(pdf, titles, 1)}
        orphans = set(orphaned_sections(pdf, titles, new)) - force
        stable, pages = new == pages, new
        if orphans:
            force |= orphans
        elif stable:
            break

    png_stem = paths["dir"] / f"Kapoor_Daily_{date}_Sample_FrontPage"
    subprocess.run(["pdftoppm", "-png", "-r", "160", "-f", "1", "-l", "1", "-singlefile", str(pdf), str(png_stem)], check=True)
    print(pdf)
    print(png_stem.with_suffix(".png"))


if __name__ == "__main__":
    main()
