"""Load configuration and edition content."""

import datetime as dt
from pathlib import Path

import yaml

from . import ROOT


def load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_config() -> dict:
    cfg = load_yaml(ROOT / "config" / "profile.yaml")
    cfg["sources"] = load_yaml(ROOT / "config" / "sources.yaml")
    cfg["preferences"] = load_yaml(ROOT / "config" / "preferences.yaml")
    return cfg


def edition_dir(date: dt.date) -> Path:
    return ROOT / "editions" / date.isoformat()


def load_edition(date: dt.date) -> dict:
    d = edition_dir(date)
    for name in ("content.yaml", "content.json"):
        if (d / name).exists():
            content = load_yaml(d / name)  # YAML is a superset of JSON
            break
    else:
        raise FileNotFoundError(f"No content.yaml/json in {d}")
    content.setdefault("stories", [])
    content.setdefault("world_in_brief", [])
    content.setdefault("portfolio", {})
    content.setdefault("realestate", {})
    content.setdefault("research", {"ideas": []})
    content.setdefault("action_board", {})
    content.setdefault("market_snapshot", [])
    content.setdefault("graphics", {})
    return content


def previous_editions(date: dt.date, days: int = 3) -> list[dict]:
    """Content of the last few editions, used for cross-day deduplication."""
    out = []
    for i in range(1, days + 1):
        try:
            out.append(load_edition(date - dt.timedelta(days=i)))
        except FileNotFoundError:
            continue
    return out
