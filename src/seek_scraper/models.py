"""Plain data classes for jobs, job details, companies and search facets.

Every model has ``to_dict()`` (JSON), a flat CSV form and a short table layout.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Union

from .markets import MARKETS

Number = Union[int, float]

_PERIOD_SHORT = {"hour": "/hr", "day": "/day", "week": "/wk", "month": "/mo", "year": "/yr"}


def salary_text(
    low: Number | None, high: Number | None, period: str | None, currency: str | None
) -> str:
    """A short salary such as ``AUD 120,000-140,000/yr`` (empty when there is none)."""
    if low is None and high is None:
        return ""

    def fmt(v: Number) -> str:
        return f"{v:,.0f}" if float(v).is_integer() else f"{v:,.2f}"

    if low is not None and high is not None:
        amount = fmt(low) if low == high else f"{fmt(low)}-{fmt(high)}"
    elif low is not None:
        amount = f"{fmt(low)}+"
    else:
        amount = f"up to {fmt(high)}"  # type: ignore[arg-type]
    return f"{currency + ' ' if currency else ''}{amount}{_PERIOD_SHORT.get(period or '', '')}"


def _date(value: str | None) -> str:
    return (value or "")[:10]


@dataclass
class Job:
    """One job from a search result page."""

    job_id: str
    title: str
    url: str
    market: str
    company: str | None = None
    advertiser_id: str | None = None
    private_advertiser: bool = False
    company_profile_id: str | None = None
    location: str | None = None
    locations: list[str] = field(default_factory=list)
    location_hierarchy: list[str] = field(default_factory=list)
    country_code: str | None = None
    classification: str | None = None
    classification_id: str | None = None
    subclassification: str | None = None
    subclassification_id: str | None = None
    work_types: list[str] = field(default_factory=list)
    work_arrangements: list[str] = field(default_factory=list)
    salary_label: str | None = None
    salary_min: Number | None = None
    salary_max: Number | None = None
    salary_period: str | None = None
    salary_currency: str | None = None
    teaser: str | None = None
    bullet_points: list[str] = field(default_factory=list)
    badges: list[str] = field(default_factory=list)
    is_featured: bool = False
    listed_at: str | None = None
    listed_ago: str | None = None
    logo_url: str | None = None
    role_id: str | None = None
    #: The keywords and location of the search that found this job.
    search_keywords: str | None = None
    search_where: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_row(self) -> dict[str, Any]:
        return self.to_dict()

    @property
    def salary(self) -> str:
        return salary_text(
            self.salary_min, self.salary_max, self.salary_period, self.salary_currency
        )

    TABLE_HEADER = ("job_id", "listed", "title", "company", "location", "work type", "salary")

    def table_row(self) -> tuple[str, ...]:
        return (
            self.job_id,
            _date(self.listed_at),
            self.title,
            self.company or "",
            self.location or "",
            ", ".join(self.work_types + self.work_arrangements),
            self.salary or (self.salary_label or ""),
        )


@dataclass
class SearchPage:
    """One page of search results."""

    market: str
    page: int
    page_size: int
    total: int
    jobs: list[Job]
    location: str | None = None
    location_id: str | None = None
    sort: str | None = None
    url: str | None = None

    #: SEEK stops serving results past roughly the 550th job of any search.
    RESULT_CAP = 550

    @property
    def has_next(self) -> bool:
        if len(self.jobs) < self.page_size:
            return False
        reachable = min(self.total, self.RESULT_CAP)
        return (self.page + 1) * self.page_size <= self.RESULT_CAP and (
            self.page * self.page_size < reachable
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["has_next"] = self.has_next
        return data


@dataclass
class Company:
    """The employer's SEEK company profile, when it has one."""

    id: str | None = None
    name: str | None = None
    slug: str | None = None
    url: str | None = None
    industry: str | None = None
    size: str | None = None
    website: str | None = None
    overview: str | None = None
    rating: float | None = None
    reviews_count: int | None = None
    perks: list[str] = field(default_factory=list)
    logo_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class JobDetails:
    """Everything a job page shows."""

    job_id: str
    title: str
    url: str
    market: str
    status: str | None = None
    is_expired: bool = False
    listed_at: str | None = None
    expires_at: str | None = None
    company: str | None = None
    advertiser_id: str | None = None
    advertiser_name: str | None = None
    advertiser_verified: bool | None = None
    advertiser_registered_at: str | None = None
    private_advertiser: bool = False
    location: str | None = None
    area: str | None = None
    suburb: str | None = None
    region: str | None = None
    state: str | None = None
    postcode: str | None = None
    country: str | None = None
    country_code: str | None = None
    classification: str | None = None
    classification_id: str | None = None
    subclassification: str | None = None
    subclassification_id: str | None = None
    work_type: str | None = None
    work_arrangements: list[str] = field(default_factory=list)
    salary_label: str | None = None
    salary_min: Number | None = None
    salary_max: Number | None = None
    salary_period: str | None = None
    salary_currency: str | None = None
    abstract: str | None = None
    bullet_points: list[str] = field(default_factory=list)
    description_html: str = ""
    description_text: str = ""
    #: The employer's screening questions shown when you apply.
    questions: list[str] = field(default_factory=list)
    video_url: str | None = None
    logo_url: str | None = None
    cover_image_url: str | None = None
    #: True when "Apply" sends you to the employer's own site.
    applies_on_employer_site: bool = False
    is_verified: bool | None = None
    role: str | None = None
    company_jobs_url: str | None = None
    company_profile: Company | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_row(self) -> dict[str, Any]:
        """Flat CSV form: company profile fields become ``company_*`` columns."""
        row = self.to_dict()
        row.pop("description_html", None)
        profile = row.pop("company_profile") or {}
        for key in (
            "name",
            "industry",
            "size",
            "website",
            "rating",
            "reviews_count",
            "perks",
            "url",
        ):
            row[f"company_{key}"] = profile.get(key)
        return row

    @property
    def salary(self) -> str:
        return salary_text(
            self.salary_min, self.salary_max, self.salary_period, self.salary_currency
        )

    TABLE_HEADER = ("job_id", "status", "title", "company", "location", "salary", "rating")

    def table_row(self) -> tuple[str, ...]:
        profile = self.company_profile
        rating = ""
        if profile and profile.rating is not None:
            rating = f"{profile.rating} ({profile.reviews_count or 0} reviews)"
        return (
            self.job_id,
            self.status or "",
            self.title,
            self.company or "",
            self.location or "",
            self.salary or (self.salary_label or ""),
            rating,
        )


@dataclass
class Facets:
    """How the jobs of one search split by work type, arrangement and salary."""

    market: str
    keywords: str | None
    where: str | None
    location: str | None
    total: int
    work_types: list[dict[str, Any]] = field(default_factory=list)
    work_arrangements: list[dict[str, Any]] = field(default_factory=list)
    #: Jobs whose advertised (or hidden) salary is at least ``amount``.
    salary_at_least: list[dict[str, Any]] = field(default_factory=list)
    related_searches: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def csv_rows(self) -> list[dict[str, Any]]:
        base = {"market": self.market, "keywords": self.keywords, "location": self.location}
        rows = [{**base, "facet": "total", "value": "all jobs", "count": self.total}]
        rows += [
            {**base, "facet": "work_type", "value": r["label"], "count": r["count"]}
            for r in self.work_types
        ]
        rows += [
            {**base, "facet": "work_arrangement", "value": r["label"], "count": r["count"]}
            for r in self.work_arrangements
        ]
        rows += [
            {**base, "facet": "salary_at_least", "value": r["amount"], "count": r["count"]}
            for r in self.salary_at_least
        ]
        rows += [
            {**base, "facet": "related_search", "value": r["keywords"], "count": r["total_jobs"]}
            for r in self.related_searches
        ]
        return rows

    TABLE_HEADER = ("facet", "value", "jobs")

    def table_rows(self) -> list[tuple[str, ...]]:
        currency = MARKETS[self.market].currency if self.market in MARKETS else ""
        out = []
        for row in self.csv_rows():
            value = row["value"]
            if row["facet"] == "salary_at_least":
                value = f"{currency} {value:,}".strip()
            out.append((row["facet"], str(value), str(row["count"])))
        return out
