"""Scrape SEEK, Jobstreet and JobsDB through the ScrapeUnblocker ``getPageSource`` API.

:class:`SeekScraper` uses the official ``scrapeunblocker`` SDK for every request:

* **Search** calls the JSON search API the sites' own search pages use, up to 100
  jobs per request (see :mod:`seek_scraper.urls`).
* **Job details** read the data embedded in the server-rendered job page
  (see :mod:`seek_scraper.parsing`). Job pages are routed through the market's own
  country unless you choose another.

No browser rendering is needed, so each page is one plain ``getPageSource`` call.
Throttled, blocked and timed-out requests are retried with doubling backoff; a response
without the expected data is fetched once more, then raises :class:`ParseError`;
unknown job ids raise :class:`JobNotFoundError`.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable, Iterator
from typing import Any, Callable

from .errors import InputError, JobNotFoundError, ParseError, SeekError
from .markets import Market, get_market
from .models import Facets, Job, JobDetails, SearchPage
from .monitor import load_seen, new_jobs, now_iso, save_seen
from .parsing import parse_facets, parse_job_page, parse_search
from .urls import MAX_PAGE_SIZE, SearchFilters, job_url, parse_job_ref, search_url

_TRANSIENT_NAMES = (
    "UpstreamOutageError",
    "RateLimitError",
    "ScrapeTimeoutError",
    "BrowserTimeoutError",
    "BlockedError",
    "ServerError",
    "ConnectionError",
)
_NOT_FOUND_NAMES = ("TargetNotFoundError",)

log = logging.getLogger(__name__)


def _is_named(error: BaseException, *names: str) -> bool:
    return any(cls.__name__ in names for cls in type(error).__mro__)


class _BadAnswer(Exception):
    """A response without the expected data (fetched once more)."""


class _NotFound(SeekError):
    """The target answered 404."""


class SeekScraper:
    """Job search, job details, facet counts and new-job alerts for SEEK's job sites.

    Args:
        api_key: Your ScrapeUnblocker API key. Defaults to the
            ``SCRAPEUNBLOCKER_KEY`` environment variable (read by the SDK).
        market: Default site: ``au``, ``nz`` (SEEK), ``my``, ``sg``, ``ph``, ``id``
            (Jobstreet), ``hk`` or ``th`` (JobsDB). Every method also takes ``market=``.
        client: A ready ``scrapeunblocker.Client`` (or anything with a compatible
            ``get_page_source``); handy for tests.
        country: Two-letter country to route every request through. By default search
            calls are not routed and job pages go through the market's own country.
        max_retries: Extra attempts for a request that fails transiently.
        backoff: Seconds before the first retry; doubles on each retry.
        timeout: Seconds to wait for one API response.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        market: str | Market = "au",
        client: Any = None,
        country: str | None = None,
        max_retries: int = 3,
        backoff: float = 2.0,
        timeout: float = 180.0,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if client is None:
            from scrapeunblocker import Client

            client = Client(api_key=api_key, timeout=timeout)
        self.client = client
        self.market = get_market(market)
        self.country = country.strip().lower() if country else None
        self.max_retries = max_retries
        self.backoff = backoff
        self.sleep = sleep
        #: Number of API requests made so far.
        self.requests = 0

    # -- fetching ----------------------------------------------------------------------

    def _market(self, market: str | Market | None) -> Market:
        return self.market if market is None else get_market(market)

    def _get(self, url: str, country: str | None) -> str:
        kwargs: dict[str, Any] = {}
        if country:
            kwargs["proxy_country"] = country
        self.requests += 1
        try:
            body = self.client.get_page_source(url, **kwargs)
        except Exception as exc:
            if _is_named(exc, *_NOT_FOUND_NAMES):
                raise _NotFound(f"404 for {url}") from exc
            raise
        return body if isinstance(body, str) else str(body)

    def fetch(self, url: str, parse: Callable[[str], Any], *, country: str | None = None) -> Any:
        """Fetch ``url`` and return ``parse(body)``.

        Transient SDK errors are retried with doubling backoff. If ``parse`` raises
        ``ValueError`` the URL is fetched once more, then :class:`ParseError` is raised.
        A 404 is not retried.
        """
        attempt = 0
        bad_answers = 0
        while True:
            try:
                body = self._get(url, country)
                try:
                    return parse(body)
                except ValueError as exc:
                    bad_answers += 1
                    if bad_answers > 1:
                        raise ParseError(f"{exc} ({url})") from None
                    raise _BadAnswer(str(exc)) from None
            except (SeekError, InputError):
                raise
            except Exception as exc:
                retryable = isinstance(exc, _BadAnswer) or _is_named(exc, *_TRANSIENT_NAMES)
                if not retryable or attempt >= self.max_retries:
                    if isinstance(exc, _BadAnswer):
                        raise ParseError(f"{exc} ({url})") from None
                    raise
                reason = str(exc) if isinstance(exc, _BadAnswer) else type(exc).__name__
                log.info("retrying %s after %s", url, reason)
                self.sleep(self.backoff * (2**attempt))
                attempt += 1

    # -- search ------------------------------------------------------------------------

    def search(
        self,
        keywords: str | None = None,
        where: str | None = None,
        filters: SearchFilters | None = None,
        *,
        market: str | Market | None = None,
        page: int = 1,
        page_size: int = MAX_PAGE_SIZE,
    ) -> SearchPage:
        """One page of search results (up to 100 jobs).

        ``where`` is free text the way you would type it on the site: ``"Sydney"``,
        ``"All Melbourne VIC"``, ``"Parramatta"``, ``"Kuala Lumpur"``. SEEK resolves it
        and the page's ``location`` says what it matched. Leave it out to search the
        whole country.
        """
        site = self._market(market)
        url = search_url(site, keywords, where, filters, page=page, page_size=page_size)

        def parse(body: str) -> SearchPage:
            return parse_search(body, site, page, page_size, url)

        try:
            result = self.fetch(url, parse, country=self.country)
        except _NotFound as exc:
            raise SeekError(f"{site.name} search API answered 404 ({url})") from exc
        if where and where.strip() and result.location is None and result.total == 0:
            log.warning("%s did not recognise the location %r", site.name, where)
        for job in result.jobs:
            job.search_keywords = keywords or None
            job.search_where = where or None
        return result

    def iter_pages(
        self,
        keywords: str | None = None,
        where: str | None = None,
        filters: SearchFilters | None = None,
        *,
        market: str | Market | None = None,
        max_pages: int | None = None,
        page_size: int = MAX_PAGE_SIZE,
        start_page: int = 1,
    ) -> Iterator[SearchPage]:
        """Result pages from ``start_page`` until the last one or ``max_pages``."""
        page = start_page
        fetched = 0
        while max_pages is None or fetched < max_pages:
            result = self.search(
                keywords, where, filters, market=market, page=page, page_size=page_size
            )
            fetched += 1
            yield result
            if not result.has_next:
                return
            page += 1

    def search_jobs(
        self,
        keywords: str | None = None,
        where: str | None = None,
        filters: SearchFilters | None = None,
        *,
        market: str | Market | None = None,
        limit: int | None = 100,
    ) -> list[Job]:
        """Up to ``limit`` jobs for one search, reading as many pages as needed.

        ``limit=None`` reads every page SEEK serves (it stops after about 550 jobs per
        search; narrow the search or split it by location to collect more).
        """
        if limit is not None and limit < 1:
            raise InputError("limit must be 1 or more")
        page_size = MAX_PAGE_SIZE if limit is None else min(limit, MAX_PAGE_SIZE)
        jobs: list[Job] = []
        for result in self.iter_pages(keywords, where, filters, market=market, page_size=page_size):
            jobs.extend(result.jobs)
            if limit is not None and len(jobs) >= limit:
                return jobs[:limit]
        return jobs

    def collect(
        self,
        keywords: Iterable[str | None] = (None,),
        wheres: Iterable[str | None] = (None,),
        filters: SearchFilters | None = None,
        *,
        market: str | Market | None = None,
        limit_per_search: int | None = 100,
    ) -> list[Job]:
        """Run every keywords x location search and merge the jobs, deduplicated by id.

        A job found by several searches is kept once, with the first search that found it.
        """
        seen: set[str] = set()
        merged: list[Job] = []
        places = list(wheres) or [None]
        for words in list(keywords) or [None]:
            for where in places:
                for job in self.search_jobs(
                    words, where, filters, market=market, limit=limit_per_search
                ):
                    if job.job_id in seen:
                        continue
                    seen.add(job.job_id)
                    merged.append(job)
        return merged

    def facets(
        self,
        keywords: str | None = None,
        where: str | None = None,
        filters: SearchFilters | None = None,
        *,
        market: str | Market | None = None,
    ) -> Facets:
        """Job counts by work type, work arrangement and salary floor, plus related
        searches, for one search (a single request)."""
        site = self._market(market)
        url = search_url(site, keywords, where, filters, page=1, page_size=1, facets=True)

        def parse(body: str) -> Facets:
            return parse_facets(body, site, keywords, where)

        try:
            return self.fetch(url, parse, country=self.country)
        except _NotFound as exc:
            raise SeekError(f"{site.name} search API answered 404 ({url})") from exc

    # -- job details -------------------------------------------------------------------

    def job(self, ref: str | int, *, market: str | Market | None = None) -> JobDetails:
        """Full details for a job id or a job URL from any of the eight sites.

        Expired jobs still load (``status`` is ``"Expired"``); unknown ids raise
        :class:`JobNotFoundError`.
        """
        site, job_id = parse_job_ref(ref, self._market(market))
        url = job_url(site, job_id)

        def parse(page: str) -> JobDetails:
            return parse_job_page(page, site, job_id)

        try:
            return self.fetch(url, parse, country=self.country or site.country)
        except _NotFound as exc:
            raise JobNotFoundError(f"{site.name} has no job {job_id}") from exc

    def jobs(
        self,
        refs: Iterable[str | int],
        *,
        market: str | Market | None = None,
        skip_missing: bool = True,
    ) -> Iterator[JobDetails]:
        """Details for several jobs; unknown ids are logged and skipped by default."""
        for ref in refs:
            try:
                yield self.job(ref, market=market)
            except JobNotFoundError as exc:
                if not skip_missing:
                    raise
                log.warning("%s", exc)

    # -- alerts ------------------------------------------------------------------------

    def watch(
        self,
        state_path: str,
        keywords: Iterable[str | None] = (None,),
        wheres: Iterable[str | None] = (None,),
        filters: SearchFilters | None = None,
        *,
        market: str | Market | None = None,
        limit_per_search: int | None = 100,
    ) -> list[Job]:
        """Jobs that are new since the last run with the same ``state_path``.

        Sorts by listing date unless ``filters.sort`` says otherwise. The first run
        returns every current job and saves them as the baseline.
        """
        filters = filters or SearchFilters(sort="date")
        jobs = self.collect(
            keywords, wheres, filters, market=market, limit_per_search=limit_per_search
        )
        seen = load_seen(state_path)
        fresh, updated = new_jobs(jobs, seen, now_iso())
        save_seen(state_path, updated)
        if seen is None:
            log.info("first run: saved %d jobs to %s as the baseline", len(jobs), state_path)
        return fresh
