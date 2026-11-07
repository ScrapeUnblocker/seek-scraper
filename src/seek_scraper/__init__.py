"""Scrape SEEK, Jobstreet and JobsDB jobs via the ScrapeUnblocker API.

One platform, eight job sites: SEEK Australia and New Zealand, Jobstreet Malaysia,
Singapore, the Philippines and Indonesia, and JobsDB Hong Kong and Thailand. Search
jobs with the sites' own filters, open full job details, count jobs by work type,
work arrangement and salary, and get alerts for new jobs::

    from seek_scraper import SearchFilters, SeekScraper

    seek = SeekScraper()  # reads SCRAPEUNBLOCKER_KEY from the environment
    jobs = seek.search_jobs(
        "data engineer",
        "All Sydney NSW",
        SearchFilters(work_arrangements=["hybrid", "remote"], listed_within_days=7),
        limit=50,
    )
    details = seek.job(jobs[0].job_id)

    jobstreet = seek.search_jobs("accountant", "Kuala Lumpur", market="my", limit=20)

Every request goes through the ScrapeUnblocker ``getPageSource`` API using the
official ``scrapeunblocker`` SDK:
https://scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos
"""

from .errors import InputError, JobNotFoundError, ParseError, SeekError
from .export import render, to_csv_file, write
from .markets import CLASSIFICATIONS, MARKETS, Classification, Market, get_market
from .models import Company, Facets, Job, JobDetails, SearchPage
from .salary import Salary, parse_salary
from .scraper import SeekScraper
from .urls import SearchFilters, job_url, parse_job_ref, search_url

__version__ = "0.1.0"

__all__ = [
    "CLASSIFICATIONS",
    "Classification",
    "Company",
    "Facets",
    "InputError",
    "Job",
    "JobDetails",
    "JobNotFoundError",
    "MARKETS",
    "Market",
    "ParseError",
    "Salary",
    "SearchFilters",
    "SearchPage",
    "SeekError",
    "SeekScraper",
    "__version__",
    "get_market",
    "job_url",
    "parse_job_ref",
    "parse_salary",
    "render",
    "search_url",
    "to_csv_file",
    "write",
]
