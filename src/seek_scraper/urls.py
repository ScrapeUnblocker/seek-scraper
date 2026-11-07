"""Build SEEK search API URLs and job page URLs.

The search API takes the same query parameters as the sites' own search pages
(``keywords``, ``where``, ``classification``, ``worktype``, ``workarrangement``,
``salaryrange``, ``salarytype``, ``daterange``, ``sortmode``, ``page``, ``pageSize``)
plus the market's ``siteKey`` and ``locale``. It echoes them back under
``searchParams``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlencode, urlsplit

from .errors import InputError
from .markets import (
    LISTED_WITHIN_DAYS,
    SALARY_TYPES,
    SORTS,
    Market,
    classification_id,
    get_market,
    market_for_host,
    work_arrangement_id,
    work_type_id,
)

#: The search API's largest page.
MAX_PAGE_SIZE = 100
SEARCH_PATH = "/api/jobsearch/v5/search"
#: Facets SEEK reports counts for (``facets=`` on the search API).
FACETS = ("salaryMin", "workArrangement", "workType")

_JOB_PATH = re.compile(r"/job/(\d+)")


@dataclass
class SearchFilters:
    """Search filters. Every field is optional.

    Classifications take ids (``6281``), slugs or short aliases (``it``, ``healthcare``);
    work types take ``full-time``, ``part-time``, ``contract`` or ``casual``; work
    arrangements take ``on-site``, ``hybrid`` or ``remote``. Salary bounds use the
    ``salary_type`` period (SEEK's default is annual in Australia and New Zealand).
    """

    classifications: list[str] = field(default_factory=list)
    subclassifications: list[str] = field(default_factory=list)
    work_types: list[str] = field(default_factory=list)
    work_arrangements: list[str] = field(default_factory=list)
    salary_min: int | None = None
    salary_max: int | None = None
    salary_type: str | None = None
    listed_within_days: int | None = None
    sort: str = "relevance"

    def params(self) -> dict[str, str]:
        """The query parameters for these filters (validated)."""
        out: dict[str, str] = {}
        if self.classifications:
            out["classification"] = ",".join(classification_id(c) for c in self.classifications)
        if self.subclassifications:
            subs = [str(s).strip() for s in self.subclassifications]
            if not all(s.isdigit() for s in subs):
                raise InputError(
                    "subclassifications must be numeric ids (see a job's subclassification_id)"
                )
            out["subclassification"] = ",".join(subs)
        if self.work_types:
            out["worktype"] = ",".join(work_type_id(w) for w in self.work_types)
        if self.work_arrangements:
            out["workarrangement"] = ",".join(
                work_arrangement_id(w) for w in self.work_arrangements
            )
        low, high = self.salary_min, self.salary_max
        for value in (low, high):
            if value is not None and value < 0:
                raise InputError("salary bounds must be positive")
        if low is not None and high is not None and high < low:
            raise InputError("salary_max must not be below salary_min")
        if low is not None or high is not None:
            out["salaryrange"] = f"{int(low or 0)}-{'' if high is None else int(high)}"
        if self.salary_type:
            kind = self.salary_type.strip().lower()
            if kind not in SALARY_TYPES:
                raise InputError(f"salary type must be one of: {', '.join(SALARY_TYPES)}")
            out["salarytype"] = kind
        if self.listed_within_days is not None:
            days = int(self.listed_within_days)
            if days not in LISTED_WITHIN_DAYS:
                choices = ", ".join(str(d) for d in LISTED_WITHIN_DAYS)
                raise InputError(f"listed_within_days must be one of: {choices}")
            out["daterange"] = str(days)
        sort = (self.sort or "relevance").strip().lower()
        if sort not in SORTS:
            raise InputError(f"sort must be one of: {', '.join(SORTS)}")
        if sort != "relevance":
            out["sortmode"] = SORTS[sort]
        return out


def search_url(
    market: str | Market,
    keywords: str | None = None,
    where: str | None = None,
    filters: SearchFilters | None = None,
    *,
    page: int = 1,
    page_size: int = MAX_PAGE_SIZE,
    facets: bool = False,
) -> str:
    """The search API URL for one page of results.

    With ``facets=True`` the response also counts jobs per work type, work arrangement
    and salary floor, and lists related searches.
    """
    site = get_market(market)
    if page < 1:
        raise InputError("page must be 1 or more")
    if not 1 <= page_size <= MAX_PAGE_SIZE:
        raise InputError(f"page_size must be between 1 and {MAX_PAGE_SIZE}")
    params: dict[str, str] = {"siteKey": site.site_key, "locale": site.locale}
    if keywords and keywords.strip():
        params["keywords"] = keywords.strip()
    if where and where.strip():
        params["where"] = where.strip()
    params.update((filters or SearchFilters()).params())
    params["page"] = str(page)
    params["pageSize"] = str(page_size)
    if facets:
        params["facets"] = ",".join(FACETS)
        params["include"] = "relatedsearches"
    return f"{site.base_url}{SEARCH_PATH}?{urlencode(params)}"


def job_url(market: str | Market, job_id: str | int) -> str:
    """The job page URL, e.g. ``https://www.seek.com.au/job/12345678``."""
    return f"{get_market(market).base_url}/job/{job_id}"


def parse_job_ref(ref: str | int, market: str | Market = "au") -> tuple[Market, str]:
    """``(market, job_id)`` for a job id or any SEEK, Jobstreet or JobsDB job URL.

    A URL picks its own market from the hostname; a bare id uses ``market``.
    Search page URLs with ``?jobId=`` (the split view) work too.
    """
    text = str(ref).strip()
    if text.isdigit():
        return get_market(market), text
    parts = urlsplit(text if "//" in text else f"https://{text}")
    site = market_for_host(parts.hostname or "")
    match = _JOB_PATH.search(parts.path)
    job_id = match.group(1) if match else None
    if job_id is None:
        values = parse_qs(parts.query).get("jobId") or []
        job_id = values[0] if values and values[0].isdigit() else None
    if site is None or job_id is None:
        raise InputError(f"not a SEEK, Jobstreet or JobsDB job id or URL: {ref!r}")
    return site, job_id
