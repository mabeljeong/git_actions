"""JPMC (Oracle HCM Cloud) career site scraper.

Oracle HCM exposes a JSON API that the careers UI itself calls. Going through
the API is orders of magnitude faster and more robust than DOM scraping, so we
try that first and fall back to Playwright DOM extraction only if the API shape
changes.
"""

from __future__ import annotations

import json
import re
from urllib.parse import urlencode

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout

from scrapers.base import Job

COMPANY = "JPMC"

SEARCH_URL = (
    "https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/jobs"
    "?keyword=data+scientist"
    "&location=United+States"
    "&locationId=300000000289738"
    "&locationLevel=country"
    "&mode=location"
)

API_BASE = (
    "https://jpmc.fa.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
)
SITE_NUMBER = "CX_1001"


def _api_finder_params(keyword: str, location_id: str, limit: int = 50) -> str:
    finder = (
        "findReqs;siteNumber={site},"
        "facetsList=LOCATIONS;TITLES;CATEGORIES;ORGANIZATIONS;POSTING_DATES;FLEX_FIELDS,"
        "limit={limit},"
        "keyword={kw},"
        "locationId={loc},"
        "locationLevel=country,"
        "sortBy=RELEVANCY"
    ).format(site=SITE_NUMBER, limit=limit, kw=keyword, loc=location_id)
    query = {
        "onlyData": "true",
        "expand": "requisitionList.secondaryLocations,flexFieldsFacet.values",
        "finder": finder,
    }
    return urlencode(query)


def _job_url(req_id: str) -> str:
    return (
        f"https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/"
        f"{SITE_NUMBER}/job/{req_id}"
    )


def _via_api(page: Page) -> list[Job]:
    """Hit Oracle HCM's internal JSON API through the browser context.

    Running the fetch inside the page keeps cookies/headers set by the site, so
    the request is accepted the same way the UI's XHR would be.
    """
    url = f"{API_BASE}?{_api_finder_params('data scientist', '300000000289738')}"

    try:
        page.goto(SEARCH_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(1500)
    except PlaywrightTimeout:
        return []

    raw = page.evaluate(
        """async (u) => {
            const r = await fetch(u, {
                headers: { 'Accept': 'application/json' },
                credentials: 'include',
            });
            if (!r.ok) return null;
            return await r.text();
        }""",
        url,
    )
    if not raw:
        return []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []

    items = []
    for entry in data.get("items", []):
        for req in entry.get("requisitionList", []) or []:
            title = (req.get("Title") or "").strip()
            req_id = str(req.get("Id") or "").strip()
            primary = (req.get("PrimaryLocation") or "").strip()
            if not (title and req_id):
                continue
            items.append(
                Job(
                    company=COMPANY,
                    title=title,
                    location=primary or "United States",
                    url=_job_url(req_id),
                )
            )
    return items


def _via_dom(page: Page) -> list[Job]:
    """DOM fallback in case the API shape changes."""
    try:
        page.goto(SEARCH_URL, wait_until="domcontentloaded")
    except PlaywrightTimeout:
        return []

    page.wait_for_timeout(4000)

    for _ in range(5):
        page.mouse.wheel(0, 1500)
        page.wait_for_timeout(800)

    selectors = [
        "li[data-qa='searchResultItem']",
        "li.job-grid-item",
        "a[data-qa='searchResultItemLink']",
        "a.job-list-item__link",
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
                text = card.inner_text(timeout=2000)
            except Exception:
                continue
            href = None
            for link_sel in ("a[data-qa='searchResultItemLink']", "a"):
                try:
                    link = card.locator(link_sel).first
                    if link.count():
                        href = link.get_attribute("href")
                        if href:
                            break
                except Exception:
                    continue
            if not href:
                continue
            if href.startswith("/"):
                href = "https://jpmc.fa.oraclecloud.com" + href
            if href in seen_urls:
                continue
            seen_urls.add(href)

            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            title = lines[0] if lines else "Data Scientist"
            location = next(
                (
                    ln
                    for ln in lines[1:]
                    if re.search(r"[A-Za-z]", ln) and ln != title
                ),
                "",
            )
            jobs.append(
                Job(company=COMPANY, title=title, location=location, url=href)
            )
        if jobs:
            break

    return jobs


def scrape_jpmc(page: Page) -> list[Job]:
    jobs = _via_api(page)
    if jobs:
        print(f"[jpmc] API returned {len(jobs)} jobs")
        return jobs
    print("[jpmc] API returned no jobs, falling back to DOM scrape")
    jobs = _via_dom(page)
    print(f"[jpmc] DOM returned {len(jobs)} jobs")
    return jobs
