"""Build one edition: validate → rank → render (web, email, print) → print QA → report.

    python -m kapoor_daily.build --date 2026-10-27
    python -m kapoor_daily.build --date 2026-10-27 --skip-pdf
    python -m kapoor_daily.build --date 2026-10-27 --links-base https://example/archive/2026-10

Exit codes: 0 ok · 1 content failed validation (failure report written) · 2 print QA failed.
"""

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

from . import ROOT
from .loader import edition_dir, load_config, load_edition, previous_editions
from .printing import A4, A5, find_group_pages, impose_booklet, orphaned_sections, qa, typeset
from .rank import rank
from .render import SECTION_TITLES, build_context, render
from .validate import validate

ET = ZoneInfo("America/New_York")


def out_paths(date: dt.date) -> dict:
    d = ROOT / "archive" / date.strftime("%Y-%m")
    stem = f"Kapoor_Daily_{date.isoformat()}"
    return {
        "dir": d,
        "web": d / f"{stem}.html",
        "artifact": d / f"{stem}.artifact.html",
        "email": d / f"{stem}_email.html",
        "a4": d / f"{stem}_A4.pdf",
        "bound": d / f"{stem}_Bound.pdf",
        "booklet": d / f"{stem}_A5_Booklet.pdf",
        "report": d / f"{stem}_build_report.json",
        "failure": d / f"{stem}_FAILURE.md",
        "work": ROOT / "_build" / date.isoformat(),
    }


def write_failure(paths, date, errors, warnings, stage):
    paths["dir"].mkdir(parents=True, exist_ok=True)
    lines = [f"# The Kapoor Daily — build FAILED for {date.isoformat()}", "", f"Stage: **{stage}**", "",
             "## Errors (publication blocked)", *[f"- {e}" for e in errors], "",
             "## Warnings", *([f"- {w}" for w in warnings] or ["- none"]), "",
             "Fix the content (or re-run research) and rebuild. Nothing was delivered."]
    paths["failure"].write_text("\n".join(lines) + "\n")
    return paths["failure"]


def section_titles(ctx):
    """Heading text of every printed section, used to find its page number."""
    titles = {sid: t for sid, t in ctx["sections"].items() if sid != "lifestyle" or ctx["ranked"].get("lifestyle")}
    titles.update(SECTION_TITLES)
    return titles


def build_print(ctx, variant, paths, page_range):
    work = paths["work"]
    work.mkdir(parents=True, exist_ok=True)
    fonts = (ROOT / "assets" / "fonts" / "fonts.css").as_uri()
    html = work / f"print_{variant}.html"
    pdf = work / f"print_{variant}.pdf"
    skip = 2 if variant == "bound" else 1
    pages = {"front": skip}
    titles = section_titles(ctx)
    force = set()
    # Lay out, then fix what the layout got wrong: section heads stranded at the foot of a
    # page get a forced page break, and contents/"Inside" page numbers are filled in.
    # Stops once page numbers are stable and no orphan remains (at most 5 passes).
    for _ in range(5):
        html.write_text(render("print.html.j2", {**ctx, "force_break": force}, variant=variant, pages=pages, fonts_css=fonts))
        probe = typeset(html, pdf)
        new_pages = {"front": skip, **find_group_pages(pdf, titles, skip)}
        orphans = set(orphaned_sections(pdf, titles, new_pages)) - force
        stable = new_pages == pages
        pages = new_pages
        if orphans:
            force |= orphans
        elif stable:
            break
    size = A5 if variant == "booklet" else A4
    headlines = probe["headlines"]
    errors, warnings = qa(pdf, probe, size, page_range, headlines, variant)
    for sid in orphaned_sections(pdf, titles, pages):
        errors.append(f"{variant}: section head '{titles[sid]}' stranded at foot of page {pages[sid]}")
    if force:
        warnings.append(f"{variant}: forced page breaks before {sorted(force)} to keep heads with their stories")
    missing = [sid for sid in titles if sid not in pages]
    if missing:
        warnings.append(f"{variant}: could not locate page numbers for {missing}")
    return pdf, errors, warnings, pages


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", default=dt.datetime.now(ET).date().isoformat())
    ap.add_argument("--now", help="Override build time (ISO 8601) for staleness checks / tests")
    ap.add_argument("--skip-pdf", action="store_true")
    ap.add_argument("--links-base", help="URL prefix where the archive files will be reachable (for the email)")
    args = ap.parse_args(argv)

    date = dt.date.fromisoformat(args.date)
    now = dt.datetime.fromisoformat(args.now) if args.now else dt.datetime.now(ET)
    paths = out_paths(date)
    cfg = load_config()
    try:
        content = load_edition(date)
    except FileNotFoundError as e:
        f = write_failure(paths, date, [f"No researched content for {date}: {e}"], [], "load")
        print(f"FAILED: {f}")
        return 1

    report = validate(content, cfg, build_time=now)
    if not report.ok:
        f = write_failure(paths, date, report.errors, report.warnings, "validation")
        print(f"FAILED validation ({len(report.errors)} errors): {f}")
        for e in report.errors:
            print("  ✗", e)
        return 1

    log = []
    ranked = rank(content, cfg, previous_editions(date), log)
    ctx = build_context(content, cfg, ranked, report, log)
    paths["dir"].mkdir(parents=True, exist_ok=True)
    if paths["failure"].exists():
        paths["failure"].unlink()

    links = {}
    if args.links_base:
        base = args.links_base.rstrip("/")
        links = {k: f"{base}/{paths[k].name}" for k in ("web", "a4", "bound", "booklet")}

    print_files = [] if args.skip_pdf else [("A4", paths["a4"].name), ("Bound", paths["bound"].name),
                                             ("A5 booklet", paths["booklet"].name)]
    paths["web"].write_text(render("web.html.j2", ctx, standalone=True, print_files=print_files))
    paths["artifact"].write_text(render("web.html.j2", ctx, standalone=False, print_files=print_files))
    paths["email"].write_text(render("email.html.j2", ctx, links=links))

    result = {"date": date.isoformat(), "built_at": now.isoformat(), "warnings": report.warnings,
              "editorial_log": log, "outputs": {k: str(paths[k].relative_to(ROOT)) for k in ("web", "artifact", "email")},
              "print": {}}
    qa_errors = []
    if not args.skip_pdf:
        sunday = date.weekday() == 6
        rng = tuple(cfg["publication"]["print_pages"]["sunday" if sunday else "weekday"])
        for variant, key, prange in (("a4", "a4", rng), ("bound", "bound", (rng[0] + 1, rng[1] + 2)),
                                     ("booklet", "booklet", (rng[0] * 2, rng[1] * 2 + 4))):
            pdf, errs, warns, pages = build_print(ctx, variant, paths, prange)
            if variant == "booklet":
                sheets = impose_booklet(pdf, paths["booklet"])
                info = {"a5_pages": len(__import__("pypdf").PdfReader(pdf).pages), "sheet_sides": sheets}
            else:
                paths[key].write_bytes(pdf.read_bytes())
                info = {"pages": len(__import__("pypdf").PdfReader(pdf).pages), "sections": pages}
            result["print"][variant] = {"file": str(paths[key].relative_to(ROOT)), **info, "errors": errs, "warnings": warns}
            qa_errors += errs
    paths["report"].write_text(json.dumps(result, indent=2, default=str))

    print(f"Built {date}: {len(ctx['sources'])} sources, {sum(len(v) for v in ranked.values())} stories, "
          f"{len(report.warnings)} validation warnings")
    for v, r in result["print"].items():
        print(f"  {v}: {r.get('pages') or r.get('a5_pages')} pages, {len(r['errors'])} QA errors, {len(r['warnings'])} warnings")
        for e in r["errors"] + r["warnings"]:
            print("    -", e)
    if qa_errors:
        write_failure(paths, date, qa_errors, [], "print QA")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
