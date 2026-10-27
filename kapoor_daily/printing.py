"""PDF typesetting, booklet imposition and print-quality checks."""

import json
import re
import subprocess
from pathlib import Path

from pypdf import PageObject, PdfReader, PdfWriter, Transformation

from . import ROOT

MM = 72 / 25.4
A4 = (210 * MM, 297 * MM)
A5 = (148 * MM, 210 * MM)


def typeset(html: Path, pdf: Path) -> dict:
    """Render HTML to PDF with Chromium; return the layout probe."""
    probe = pdf.with_suffix(".probe.json")
    subprocess.run(["node", str(ROOT / "scripts" / "pdf.mjs"), str(html), str(pdf), str(probe)],
                   check=True, capture_output=True, text=True, timeout=180)
    data = json.loads(probe.read_text())
    probe.unlink()
    return data


def page_texts(pdf: Path) -> list[str]:
    return [re.sub(r"\s+", " ", p.extract_text() or "") for p in PdfReader(pdf).pages]


def find_group_pages(pdf: Path, group_titles: dict, skip: int) -> dict:
    """First page on which each group's heading appears (searching after the front matter)."""
    texts = [t.lower() for t in page_texts(pdf)]
    out = {}
    for gid, title in group_titles.items():
        needle = re.sub(r"\s+", " ", title.lower())
        for i in range(skip, len(texts)):
            if needle in texts[i]:
                out[gid] = i + 1
                break
    return out


def orphaned_sections(pdf: Path, titles: dict, pages: dict, min_chars: int = 220) -> list[str]:
    """Sections whose heading sits at the foot of a page with (almost) none of its content."""
    texts = page_texts(pdf)
    out = []
    for sid, p in pages.items():
        if sid not in titles or not 1 <= p <= len(texts):
            continue
        t = texts[p - 1].lower()
        i = t.find(re.sub(r"\s+", " ", titles[sid].lower()))
        if i >= 0 and len(t) - i < min_chars:
            out.append(sid)
    return out


def booklet_order(n: int) -> list[tuple[int | None, int | None]]:
    """Saddle-stitch imposition. Returns (left, right) page indexes for each sheet side.

    n is padded to a multiple of 4; None marks a blank. Sheet sides alternate front/back,
    so print duplex flipping on the short edge, then fold the stack in half.
    """
    total = (n + 3) // 4 * 4
    sides = []
    for i in range(total // 2):
        hi, lo = total - 1 - i, i
        pair = (hi, lo) if i % 2 == 0 else (lo, hi)
        sides.append(tuple(p if p < n else None for p in pair))
    return sides


def impose_booklet(a5_pdf: Path, out: Path) -> int:
    src = PdfReader(a5_pdf)
    w, h = A5
    writer = PdfWriter()
    sides = booklet_order(len(src.pages))
    for left, right in sides:
        sheet = PageObject.create_blank_page(width=A4[1], height=A4[0])  # A4 landscape
        for idx, x in ((left, 0), (right, w)):
            if idx is None:
                continue
            pg = src.pages[idx]
            sx = w / float(pg.mediabox.width)
            sy = h / float(pg.mediabox.height)
            sheet.merge_transformed_page(pg, Transformation().scale(sx, sy).translate(x, 0))
        writer.add_page(sheet)
    writer.add_metadata({"/Title": "The Kapoor Daily — A5 booklet (imposed on A4)"})
    with open(out, "wb") as f:
        writer.write(f)
    return len(sides)


def qa(pdf: Path, probe: dict, expect_size, page_range, headlines: list[str], label: str) -> tuple[list, list]:
    """Return (errors, warnings) for one PDF."""
    errors, warnings = [], []
    reader = PdfReader(pdf)
    n = len(reader.pages)
    for i, p in enumerate(reader.pages):
        w, h = float(p.mediabox.width), float(p.mediabox.height)
        if abs(w - expect_size[0]) > 1.5 or abs(h - expect_size[1]) > 1.5:
            errors.append(f"{label}: page {i + 1} is {w / MM:.1f}×{h / MM:.1f} mm, expected "
                          f"{expect_size[0] / MM:.0f}×{expect_size[1] / MM:.0f} mm")
            break
    lo, hi = page_range
    if not lo <= n <= hi:
        warnings.append(f"{label}: {n} pages (target {lo}–{hi})")
    for issue in probe.get("issues", []):
        errors.append(f"{label}: {issue['kind']} — {issue['tag']} '{issue['label']}'")
    if not any("UnifrakturMaguntia" in f for f in probe.get("fonts", [])) or \
       not any("Source Serif 4" in f for f in probe.get("fonts", [])):
        errors.append(f"{label}: vendored fonts did not load ({probe.get('fonts')})")

    # Every story must be present (nothing dropped/truncated) and no headline may be
    # stranded at the foot of a page with its body on the next page.
    texts = page_texts(pdf)
    flat = " ".join(texts)
    norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
    flat_n = norm(flat)
    for hl in headlines:
        if norm(hl)[:60] not in flat_n:
            errors.append(f"{label}: headline missing from PDF text: '{hl[:60]}'")
    for i, t in enumerate(texts[:-1]):
        tail = norm(t)[-90:]
        for hl in headlines:
            key = norm(hl)[-40:]
            if len(key) >= 25 and key in tail and norm(texts[i + 1]).find(key) == -1:
                if norm(t).endswith(key) or len(tail.split(key)[-1]) < 30:
                    warnings.append(f"{label}: possible stranded headline at foot of page {i + 1}: '{hl[:50]}'")
    return errors, warnings
