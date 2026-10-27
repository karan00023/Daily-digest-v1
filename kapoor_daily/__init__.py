"""The Kapoor Daily: a personalised newspaper generator.

Research is done by an agent (see docs/DAILY_RUNBOOK.md) and written to
editions/YYYY-MM-DD/content.yaml. This package validates, ranks, deduplicates
and typesets that content into web, email and print editions.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
