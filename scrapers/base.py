"""Shared helpers for scrapers: Job dataclass, browser context, US filter."""

from __future__ import annotations

import hashlib
import re
from contextlib import contextmanager
from dataclasses import dataclass

from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth


@dataclass(frozen=True)
class Job:
    company: str
    title: str
    location: str
    url: str
    posted_at: str = ""
    company_size: str = ""
    source: str = ""

    @property
    def job_id(self) -> str:
        key = f"{self.company}|{self.url}".encode("utf-8")
        return hashlib.sha1(key).hexdigest()

    def to_dict(self) -> dict:
        return {
            "company": self.company,
            "title": self.title,
            "location": self.location,
            "url": self.url,
            "posted_at": self.posted_at,
            "company_size": self.company_size,
            "source": self.source,
            "job_id": self.job_id,
        }


@contextmanager
def launch_browser(headless: bool = True):
    """Yield (browser, page) with a stealth Chromium context."""
    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
            ignore_default_args=["--enable-automation"],
        )
        context = browser.new_context(
            locale="en-US",
            timezone_id="America/Los_Angeles",
            viewport={"width": 1365, "height": 900},
            color_scheme="light",
        )
        page = context.new_page()
        page.set_default_timeout(60000)
        try:
            yield browser, page
        finally:
            context.close()
            browser.close()


US_STATES = {
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
    "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana",
    "maine", "maryland", "massachusetts", "michigan", "minnesota",
    "mississippi", "missouri", "montana", "nebraska", "nevada",
    "new hampshire", "new jersey", "new mexico", "new york",
    "north carolina", "north dakota", "ohio", "oklahoma", "oregon",
    "pennsylvania", "rhode island", "south carolina", "south dakota",
    "tennessee", "texas", "utah", "vermont", "virginia", "washington",
    "west virginia", "wisconsin", "wyoming", "district of columbia",
}

US_STATE_ABBREVS = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI",
    "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI",
    "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC",
    "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT",
    "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}

US_LOCATION_MARKERS = {
    "united states",
    "usa",
    "u.s.",
    "u.s.a.",
    "remote - us",
    "remote, us",
    "remote (us)",
    "remote, united states",
}


def is_us_location(location: str) -> bool:
    """Return True if the free-text location looks like a US location.

    Matches if the string:
      - contains a known US marker ("united states", "usa", etc.), OR
      - contains a full US state name, OR
      - ends with a 2-letter US state abbreviation (e.g. "New York, NY").
    """
    if not location:
        return False

    low = location.lower().strip()

    if any(marker in low for marker in US_LOCATION_MARKERS):
        return True

    for state in US_STATES:
        if re.search(rf"\b{re.escape(state)}\b", low):
            return True

    tokens = re.findall(r"[A-Za-z]{2,}", location)
    for tok in tokens[-2:]:
        if tok.upper() in US_STATE_ABBREVS:
            return True

    return False
