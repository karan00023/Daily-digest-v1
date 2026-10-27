"""Turn validated, ranked content into the web, email and print HTML editions."""

import datetime as dt
import io
import re

import qrcode
import qrcode.image.svg
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from . import ROOT
from .monitors import portfolio_table, real_estate_view, unavailable_count
from .validate import domain_of, source_tier

KIND_LABEL = {"news": "News", "analysis": "Analysis", "opinion": "Opinion",
              "opportunity": "Opportunity", "context": "Context"}

# Print editions group sections into newspaper "pages" (named @page rules give each its running head).
PRINT_GROUPS = [
    ("news", "News: Brief · Local · Tech · India", ["brief", "local", "tech", "india"]),
    ("money", "Money: Property · Portfolio · Research", ["realestate", "portfolio", "research", "finance"]),
    ("life", "Life · Action Board · Sources", ["lifestyle", "actions", "sources"]),
]
# Short labels for the front-page "Inside" box and the bound contents. They must differ from the
# full section titles, which the layout pass searches for to find each section's page.
PRINT_SHORT = {"brief": "Brief", "local": "Local", "tech": "AI & Tech", "india": "India", "realestate": "Property",
               "portfolio": "Portfolio", "research": "Research", "finance": "Money & Travel",
               "lifestyle": "Lifestyle", "actions": "Action Board", "sources": "Sources"}
SECTION_TITLES = {"actions": "The Opportunity and Action Board", "sources": "Sources and Data Timestamps"}


def qr_svg(url: str, size_mm: float = 16) -> Markup:
    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=1)
    buf = io.BytesIO()
    img.save(buf)
    svg = buf.getvalue().decode()
    svg = re.sub(r"<\?xml[^>]*>", "", svg)
    svg = re.sub(r'width="[^"]*" height="[^"]*"', f'width="{size_mm}mm" height="{size_mm}mm"', svg, count=1)
    return Markup(svg)


def fmt_money(v):
    return "—" if v in (None, "") else f"${v:,.0f}"


def fmt_date_long(d: dt.date) -> str:
    return f"{d.strftime('%A')}, {d.day} {d.strftime('%B %Y')}"


def nice_published(p) -> str:
    s = str(p or "")
    try:
        d = dt.date.fromisoformat(s[:10])
        return f"{d.day} {d.strftime('%b %Y')}"
    except ValueError:
        try:
            d = dt.datetime.strptime(s, "%Y-%m").date()
            return d.strftime("%b %Y")
        except ValueError:
            return s or "date n/a"


def researched_label(value) -> str:
    try:
        ts = value if isinstance(value, dt.datetime) else dt.datetime.fromisoformat(str(value))
        return ts.strftime("%-I:%M %p ET, %-d %b")
    except ValueError:
        return str(value or "time n/a")


def build_context(content, cfg, ranked, report, log, assets_href="assets"):
    ed = content["edition"]
    date = dt.date.fromisoformat(str(ed["date"]))
    stories = {s["id"]: s for sec in ranked.values() for s in sec}
    lead = stories.get(content.get("lead")) or (ranked.get("brief") or [None])[0]
    brief = [s for s in ranked.get("brief", []) if s is not lead]
    rows = portfolio_table(content, cfg)

    # Collect every source once, preserving first appearance order.
    all_sources, seen = [], set()

    def collect(where, srcs):
        for s in srcs or []:
            if s.get("url") and s["url"] not in seen:
                seen.add(s["url"])
                all_sources.append({**s, "where": where, "tier": source_tier(s["url"], cfg["sources"]),
                                    "domain": domain_of(s["url"])})

    for sec in cfg["sections"]:
        for st in ranked.get(sec["id"], []):
            collect(sec["title"], st.get("sources"))
    pf = content["portfolio"]
    for v in pf.get("verification", []):
        collect("Portfolio — verification", v.get("sources"))
    for d in pf.get("developments", []):
        collect("Portfolio", d.get("sources"))
    for i in content["research"].get("ideas", []):
        collect("Research Desk", i.get("sources"))
    collect("Real Estate", content["realestate"].get("sources"))
    for m in content["market_snapshot"]:
        collect("Market snapshot", [{"name": m["label"] + " — " + m["as_of"], "url": m["src"]}])
    for w in content["world_in_brief"]:
        collect("World in brief", [{"name": w["text"], "url": w["src"], "published": w.get("published")}])

    words = sum(len(str(v).split()) for s in stories.values() for v in (s.get("summary"), s.get("why"), s.get("me")))
    words += sum(len(str(d.get("what", "")).split()) for d in pf.get("developments", []))
    data_notes = list(ed.get("data_notes", []))
    n_unavail = unavailable_count(rows)
    if n_unavail:
        data_notes.append(f"{n_unavail} of {len(rows)} holdings have no verified recent price today; shown as 'unavailable'.")

    return {
        "cfg": cfg,
        "ed": ed,
        "date": date,
        "date_long": fmt_date_long(date),
        "is_sunday": date.weekday() == 6,
        "title": cfg["publication"]["title"],
        "tagline": cfg["publication"]["tagline"],
        "lead": lead,
        "brief": brief,
        "ranked": ranked,
        "sections": {s["id"]: s["title"] for s in cfg["sections"]},
        "market": content["market_snapshot"],
        "graphics": content["graphics"],
        "world": content["world_in_brief"],
        "pf": pf,
        "rows": rows,
        "realestate": real_estate_view(content, cfg),
        "research": content["research"],
        "ab": content["action_board"],
        "sources": all_sources,
        "data_notes": data_notes,
        "warnings": report.warnings,
        "editorial_log": log,
        "reading_minutes": max(5, round(words / 230)),
        "kind_label": KIND_LABEL,
        "print_groups": PRINT_GROUPS,
        "print_short": PRINT_SHORT,
        "print_caps": cfg["publication"]["print_caps"],
        "digital_only": [st for sid, n in cfg["publication"]["print_caps"].items() for st in ranked.get(sid, [])[n:]],
        "force_break": set(),
        "print_titles": {**{s["id"]: s["title"] for s in cfg["sections"]}, **SECTION_TITLES},
        "assets": assets_href,
        "researched_label": researched_label(ed.get("researched_at")),
        "generated": dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z"),
    }


def env():
    e = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=select_autoescape(["html", "j2"]),
                    trim_blocks=True, lstrip_blocks=True)
    e.filters["money"] = fmt_money
    e.filters["pub"] = nice_published
    e.filters["qr"] = qr_svg
    e.filters["domain"] = domain_of
    return e


def render(template: str, ctx: dict, **extra) -> str:
    return env().get_template(template).render(**ctx, **extra)
