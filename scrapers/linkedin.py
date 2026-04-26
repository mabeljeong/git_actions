"""Best-effort LinkedIn Jobs scraper.

LinkedIn does not expose a stable public API for this use case. This module uses
the public Jobs search page first, optionally logs in when credentials are
provided, and treats company size as best-effort enrichment.
"""

from __future__ import annotations

import os
import re
from dataclasses import replace
from urllib.parse import quote_plus

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout

from scrapers.base import Job

COMPANY = "LinkedIn"
KEYWORDS = "Product data scientist"
LOCATION = "United States"
POSTED_WITHIN_SECONDS = 86400
MAX_RESULTS = int(os.environ.get("LINKEDIN_MAX_RESULTS", "25"))
MAX_ENRICH = int(os.environ.get("LINKEDIN_MAX_ENRICH", str(MAX_RESULTS)))

SEARCH_URL = (
    "https://www.linkedin.com/jobs/search/"
    f"?keywords={quote_plus(KEYWORDS)}"
    f"&location={quote_plus(LOCATION)}"
    f"&f_TPR=r{POSTED_WITHIN_SECONDS}"
    "&sortBy=DD"
)

JOB_LINK_RE = re.compile(r"/jobs/view/(\d+)")
COMPANY_SIZE_PATTERNS = (
    re.compile(r"(\d[\d,]*)\s*[-–]\s*(\d[\d,]*)\s+employees", re.I),
    re.compile(r"(\d[\d,]*)\s*\+\s+employees", re.I),
)


def _maybe_login(page: Page) -> None:
    email = os.environ.get("LINKEDIN_EMAIL", "").strip()
    password = os.environ.get("LINKEDIN_PASSWORD", "").strip()
    if not email or not password:
        return

    try:
        page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
        page.fill("input#username", email)
        page.fill("input#password", password)
        page.click("button[type='submit']")
        page.wait_for_load_state("domcontentloaded", timeout=15000)
        page.wait_for_timeout(2000)
        if "/checkpoint/" in page.url or "challenge" in page.url:
            print(
                "[linkedin] Login reached a verification challenge; "
                "continuing without assuming auth"
            )
        else:
            print("[linkedin] Login attempt completed")
    except Exception as exc:
        print(f"[linkedin] Login skipped/failed: {exc}")


def _dismiss_overlays(page: Page) -> None:
    selectors = (
        "button:has-text('Accept cookies')",
        "button:has-text('Accept All')",
        "button:has-text('Accept')",
        "button[aria-label='Dismiss']",
        "button.modal__dismiss",
        "button.contextual-sign-in-modal__modal-dismiss",
    )
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible(timeout=1000):
                loc.click(timeout=1500)
                page.wait_for_timeout(300)
        except Exception:
            continue


def _normalize_job_url(url: str) -> str:
    match = JOB_LINK_RE.search(url)
    if match:
        return f"https://www.linkedin.com/jobs/view/{match.group(1)}/"
    if url.startswith("/"):
        return f"https://www.linkedin.com{url}"
    return url


def _extract_job_id(url: str) -> str:
    match = JOB_LINK_RE.search(url)
    return match.group(1) if match else url


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _extract_cards(page: Page) -> list[Job]:
    raw_jobs = page.evaluate(
        """() => {
            const anchors = Array.from(document.querySelectorAll("a[href*='/jobs/view/']"));
            return anchors.map((anchor) => {
                const card = anchor.closest("li, article, div.base-card, div.job-card-container") || anchor;
                const titleEl = card.querySelector(
                    ".base-search-card__title, .job-card-list__title, .job-card-container__link, [data-test-job-title]"
                );
                const companyEl = card.querySelector(
                    ".base-search-card__subtitle, .job-card-container__primary-description, [data-test-job-company-name]"
                );
                const locationEl = card.querySelector(
                    ".job-search-card__location, .job-card-container__metadata-item, [data-test-job-location]"
                );
                const timeEl = card.querySelector("time");
                return {
                    href: anchor.href || anchor.getAttribute("href") || "",
                    title: (titleEl ? titleEl.innerText : anchor.innerText) || "",
                    company: (companyEl ? companyEl.innerText : "") || "",
                    location: (locationEl ? locationEl.innerText : "") || "",
                    posted: (timeEl ? (timeEl.getAttribute("datetime") || timeEl.innerText) : "") || "",
                };
            });
        }"""
    )

    jobs: list[Job] = []
    seen: set[str] = set()
    for item in raw_jobs:
        href = _normalize_job_url(_clean_text(item.get("href", "")))
        title = _clean_text(item.get("title", ""))
        company = _clean_text(item.get("company", ""))
        location = _clean_text(item.get("location", "")) or LOCATION
        posted = _clean_text(item.get("posted", ""))
        job_key = _extract_job_id(href)
        if not href or not title or job_key in seen:
            continue
        seen.add(job_key)
        jobs.append(
            Job(
                company=company or COMPANY,
                title=title,
                location=location,
                url=href,
                posted_at=posted,
                source=COMPANY,
            )
        )
        if len(jobs) >= MAX_RESULTS:
            break
    return jobs


def _parse_company_size(text: str) -> str:
    for pattern in COMPANY_SIZE_PATTERNS:
        match = pattern.search(text)
        if match:
            return _clean_text(match.group(0))
    return ""


def _enrich_company_size(page: Page, job: Job) -> Job:
    try:
        page.goto(job.url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(1500)
        _dismiss_overlays(page)
        text = _clean_text(page.locator("body").inner_text(timeout=5000))
    except Exception:
        return job

    company_size = _parse_company_size(text)
    if not company_size:
        return job
    return replace(job, company_size=company_size)


def scrape_linkedin(page: Page) -> list[Job]:
    try:
        _maybe_login(page)
        page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=60000)
    except PlaywrightTimeout:
        return []

    _dismiss_overlays(page)
    page.wait_for_timeout(2500)
    for _ in range(5):
        page.mouse.wheel(0, 1600)
        page.wait_for_timeout(700)
        _dismiss_overlays(page)

    jobs = _extract_cards(page)
    print(f"[linkedin] Search returned {len(jobs)} candidate jobs")

    enriched: list[Job] = []
    for idx, job in enumerate(jobs):
        checked = _enrich_company_size(page, job) if idx < MAX_ENRICH else job
        enriched.append(checked)

    print(f"[linkedin] After optional company-size enrichment: {len(enriched)} jobs")
    return enriched
