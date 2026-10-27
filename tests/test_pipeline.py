import copy
import datetime as dt

import pytest

from kapoor_daily.build import main as build_main
from kapoor_daily.loader import load_config, load_edition
from kapoor_daily.monitors import evaluate_listing, portfolio_table
from kapoor_daily.printing import booklet_order
from kapoor_daily.rank import dedupe, rank
from kapoor_daily.validate import validate

DATE = dt.date(2026, 10, 27)
ON_TIME = dt.datetime.fromisoformat("2026-10-27T06:30:00-04:00")


@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.fixture
def content():
    return copy.deepcopy(load_edition(DATE))


def test_sample_edition_is_valid(content, cfg):
    rep = validate(content, cfg, build_time=ON_TIME)
    assert rep.ok, rep.errors


def test_stale_research_blocks_publication(content, cfg):
    next_day = ON_TIME + dt.timedelta(days=1)
    rep = validate(content, cfg, build_time=next_day)
    assert any("STALE" in e for e in rep.errors)


def test_old_story_needs_context_flag(content, cfg):
    st = next(s for s in content["stories"] if s["id"] == "mortgage-rates")
    st.pop("context")
    rep = validate(content, cfg, build_time=ON_TIME)
    assert any("mortgage-rates" in e and "days old" in e for e in rep.errors)


def test_story_without_source_fails(content, cfg):
    content["stories"][0]["sources"] = []
    assert any("no sources" in e for e in validate(content, cfg, build_time=ON_TIME).errors)


def test_invented_holding_is_rejected(content, cfg):
    content["portfolio"]["watchlist"].append({"ticker": "NVDA", "last": "$1", "as_of": "today"})
    assert any("NVDA" in e for e in validate(content, cfg, build_time=ON_TIME).errors)


def test_price_without_timestamp_is_rejected(content, cfg):
    content["market_snapshot"][0]["as_of"] = ""
    assert any("as_of" in e for e in validate(content, cfg, build_time=ON_TIME).errors)


def test_position_sizing_blocked_without_risk_profile(content, cfg):
    content["research"]["ideas"][0]["thesis"] += " Allocate 5% of the portfolio."
    assert any("sizing" in e for e in validate(content, cfg, build_time=ON_TIME).errors)


def test_research_desk_capped_at_three(content, cfg):
    content["research"]["ideas"] = content["research"]["ideas"] * 2
    assert any("no more than 3" in e for e in validate(content, cfg, build_time=ON_TIME).errors)


def test_dedupe_within_edition_and_across_days(content):
    stories = content["stories"]
    dup = dict(stories[0], id="dup", section="local")
    log = []
    out = dedupe(stories + [dup], [], log)
    assert "dup" not in {s["id"] for s in out} and log

    log = []
    out = dedupe(stories, [{"stories": [stories[1]]}], log)
    assert stories[1]["id"] not in {s["id"] for s in out}

    log = []
    updated = dict(stories[1], update=True)
    out = dedupe([updated], [{"stories": [stories[1]]}], log)
    assert out == [updated]


def test_rank_cuts_filler_and_respects_caps(content, cfg):
    log = []
    ranked = rank(content, cfg, [], log)
    ids = {s["id"] for sec in ranked.values() for s in sec}
    assert "hoboken-walkable" not in ids  # below the drop threshold
    for sec in cfg["sections"]:
        assert len(ranked.get(sec["id"], [])) <= sec["max"]
    assert any("Cut low-relevance" in line for line in log)


def test_listing_evaluation(cfg):
    crit = cfg["real_estate"]
    ok = evaluate_listing({"price": 200000, "lot_sqft": 5000}, crit)
    assert ok["is_match"] and ok["price_per_sqft"] == 40.0
    small = evaluate_listing({"price": 185000, "lot_sqft": 3772}, crit)
    assert not small["is_match"] and "lot" in small["fails"][0]
    unknown = evaluate_listing({"price": None, "lot_sqft": 5000}, crit)
    assert "price unknown" in unknown["fails"]


def test_portfolio_table_one_row_per_holding(content, cfg):
    rows = portfolio_table(content, cfg)
    assert [r["ticker"] for r in rows] == [h["ticker"] for h in cfg["portfolio"]["holdings"]]


@pytest.mark.parametrize("n", [1, 4, 7, 8, 13, 20])
def test_booklet_imposition_is_a_permutation(n):
    sides = booklet_order(n)
    pages = [p for side in sides for p in side if p is not None]
    assert sorted(pages) == list(range(n))
    total = len(sides) * 2
    assert total % 4 == 0
    # Facing pages on each sheet side always sum to total-1 (saddle-stitch property).
    assert all(a + b == total - 1 for a, b in sides if a is not None and b is not None)


def test_missing_edition_produces_failure_report(tmp_path):
    assert build_main(["--date", "1999-01-01", "--skip-pdf"]) == 1
