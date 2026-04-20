"""Mastercard (Phenom) career site scraper.

Mastercard's careers site is powered by Phenom and exposes an internal JSON
endpoint at /api/jobs. We use that primary, with a DOM fallback.
"""

from __future__ import annotations

import json
from urllib.parse import urlencode

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout

from scrapers.base import Job

COMPANY = "Mastercard"

SEARCH_URL = (
    "https://careers.mastercard.com/us/en/search-results"
    "?keywords=data%20scientist"
    "&location=United%20States"
)

API_URL = "https://careers.mastercard.com/api/jobs"


def _api_params() -> str:
    return urlencode(
        {
            "keyword": "data scientist",
            "location": "United States",
            "country": "United States",
            "sortBy": "relevance",
            "num": "50",
        }
    )


def _accept_cookies(page: Page) -> None:
    for sel in (
        "button#onetrust-accept-btn-handler",
        "button:has-text('Accept All Cookies')",
        "button:has-text('Accept')",
    ):
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible(timeout=1500):
                loc.click(timeout=2000)
                page.wait_for_timeout(500)
                return
        except Exception:
            continue


def _via_api(page: Page) -> list[Job]:
    url = f"{API_URL}?{_api_params()}"
    try:
        page.goto(SEARCH_URL, wait_until="domcontentloaded")
        _accept_cookies(page)
        page.wait_for_timeout(1500)
    except PlaywrightTimeout:
        return []

    raw = page.evaluate(
        """async (u) => {
            try {
                const r = await fetch(u, {
                    headers: { 'Accept': 'application/json' },
                    credentials: 'include',
                });
                if (!r.ok) return null;
                return await r.text();
            } catch (e) {
                return null;
            }
        }""",
        url,
    )
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []

    candidates = []
    if isinstance(data, dict):
        for key in ("jobs", "data", "results"):
            if isinstance(data.get(key), list):
                candidates = data[key]
                break
    elif isinstance(data, list):
        candidates = data

    jobs: list[Job] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        wrapper = item.get("data") if isinstance(item.get("data"), dict) else item
        title = (wrapper.get("title") or wrapper.get("jobTitle") or "").strip()
        href = (
            wrapper.get("applyUrl")
            or wrapper.get("jobUrl")
            or wrapper.get("url")
            or wrapper.get("link")
            or ""
        ).strip()
        location = (
            wrapper.get("location")
            or wrapper.get("primaryLocation")
            or wrapper.get("city")
            or ""
        )
        if isinstance(location, list):
            location = ", ".join(str(x) for x in location if x)
        location = str(location).strip()

        if not title or not href:
            continue
        if href.startswith("/"):
            href = "https://careers.mastercard.com" + href
        jobs.append(
            Job(company=COMPANY, title=title, location=location or "United States", url=href)
        )
    return jobs


def _via_dom(page: Page) -> list[Job]:
    try:
        page.goto(SEARCH_URL, wait_until="domcontentloaded")
    except PlaywrightTimeout:
        return []

    _accept_cookies(page)
    page.wait_for_timeout(3000)

    for _ in range(6):
        page.mouse.wheel(0, 1500)
        page.wait_for_timeout(700)

    selectors = [
        "ul.jobs-list li.jobs-list-item",
        "li.jobs-list-item",
        "div.job-tile",
        "article.job-tile",
        "a.au-target[href*='/job/']",
    ]

    jobs: list[Job] = []
    seen_urls: set[str] = set()

    for sel in selectors:
        try:
            cards = page.locator(sel)
            count = cards.count()
        except Exception:
            continue
        if count == 0:
            continue

        for i in range(count):
            card = cards.nth(i)
            try:
                link = card.locator("a[href*='/job/']").first
                if not link.count():
                    link = card if card.evaluate("el => el.tagName") == "A" else None
                if link is None:
                    continue
                href = link.get_attribute("href") or ""
                title_el = card.locator(".job-title, a").first
                title = (title_el.inner_text(timeout=2000) or "").strip().splitlines()[0].strip()
                loc_el = card.locator(".job-location, .location, [data-ph-at-id='job-location-text']").first
                location = ""
                if loc_el.count():
                    location = (loc_el.inner_text(timeout=2000) or "").strip()
            except Exception:
                continue

            if not href or not title:
                continue
            if href.startswith("/"):
                href = "https://careers.mastercard.com" + href
            if href in seen_urls:
                continue
            seen_urls.add(href)

            jobs.append(
                Job(company=COMPANY, title=title, location=location, url=href)
            )
        if jobs:
            break

    return jobs


def scrape_mastercard(page: Page) -> list[Job]:
    jobs = _via_api(page)
    if jobs:
        print(f"[mastercard] API returned {len(jobs)} jobs")
        return jobs
    print("[mastercard] API returned no jobs, falling back to DOM scrape")
    jobs = _via_dom(page)
    print(f"[mastercard] DOM returned {len(jobs)} jobs")
    return jobs
