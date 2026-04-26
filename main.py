"""Orchestrator: scrape -> filter -> diff -> email -> save state.

Run locally:
    python main.py

Run as a dry run (no email, no state write):
    python main.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from notify import MissingCredentialsError, send_new_jobs_email
from scrapers import (
    Job,
    launch_browser,
    scrape_linkedin,
)

TITLE_REQUIRED_TERMS = ("product", "data scientist")
STATE_PATH = Path(__file__).parent / "state" / "seen_jobs.json"


def load_seen_ids() -> set[str]:
    if not STATE_PATH.exists():
        return set()
    try:
        raw = json.loads(STATE_PATH.read_text(encoding="utf-8") or "[]")
    except json.JSONDecodeError:
        print(f"[state] WARNING: could not parse {STATE_PATH}, starting fresh")
        return set()
    if isinstance(raw, list):
        return set(raw)
    return set()


def save_seen_ids(ids: set[str]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(sorted(ids), indent=2) + "\n", encoding="utf-8")


def title_matches(title: str) -> bool:
    low = title.lower()
    return all(term in low for term in TITLE_REQUIRED_TERMS)


def run(dry_run: bool = False) -> int:
    seen_ids = load_seen_ids()
    print(f"[state] Loaded {len(seen_ids)} previously-seen job ids")

    all_jobs: list[Job] = []
    with launch_browser(headless=True) as (_browser, page):
        try:
            all_jobs.extend(scrape_linkedin(page))
        except Exception as exc:
            print(f"[linkedin] ERROR: {exc}")

    print(f"[scrape] Raw total: {len(all_jobs)} jobs")

    filtered = [j for j in all_jobs if title_matches(j.title)]
    print(f"[filter] After title filter: {len(filtered)} jobs")

    new_jobs = [j for j in filtered if j.job_id not in seen_ids]
    print(f"[diff] {len(new_jobs)} NEW jobs vs previous state")

    for j in new_jobs:
        print(f"  + [{j.company}] {j.title} ({j.location}) -> {j.url}")

    if dry_run:
        print("[dry-run] Skipping email + state save")
        return 0

    if new_jobs:
        try:
            send_new_jobs_email(new_jobs)
        except MissingCredentialsError as exc:
            print(f"[notify] SKIPPED: {exc}")
        except Exception as exc:
            print(f"[notify] ERROR: {exc}")
            return 1

    updated = seen_ids | {j.job_id for j in filtered}
    save_seen_ids(updated)
    print(f"[state] Saved {len(updated)} job ids to {STATE_PATH}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Scrape + notify for new Product Data Scientist roles."
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Scrape and print, but don't email or update state.",
    )
    args = ap.parse_args()
    return run(dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
