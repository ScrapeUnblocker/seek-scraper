"""Parse SEEK search API responses and job pages into models.

SEEK, Jobstreet and JobsDB share one platform:

* **Search** is a JSON API (``/api/jobsearch/v5/search``) that the sites' own search
  pages call. Through ``getPageSource`` the JSON comes back either as-is or inside the
  browser's plain-text view (``<pre>`` with HTML escaping); :func:`unwrap_json` handles
  both.
* **Job pages** (``/job/<id>``) are server-rendered and carry the whole job in a
  ``window.SEEK_REDUX_DATA = {...}`` script: description, salary, location parts,
  advertiser, screening questions and the employer's company profile.
"""

from __future__ import annotations

import html
import json
import re
from typing import Any

from .errors import JobNotFoundError
from .markets import Market
from .models import Company, Facets, Job, JobDetails, SearchPage
from .salary import parse_salary

_PRE = re.compile(r"<pre[^>]*>(.*?)</pre>", re.DOTALL | re.IGNORECASE)
_DECODER = json.JSONDecoder()


def unwrap_json(body: Any) -> Any:
    """The JSON value in an API response: raw JSON, or JSON shown in a ``<pre>`` block."""
    if isinstance(body, (dict, list)):
        return body
    text = (body or "").strip() if isinstance(body, str) else str(body or "")
    if text[:1] in "{[" and text:
        return json.loads(text)
    match = _PRE.search(text)
    if match:
        return json.loads(html.unescape(match.group(1)))
    raise ValueError("response is not JSON")


def window_json(page: str, name: str) -> Any:
    """The value assigned to ``window.<name>`` in a page's scripts, or ``None``."""
    match = re.search(r"window\." + re.escape(name) + r"\s*=\s*", page or "")
    if not match:
        return None
    try:
        value, _ = _DECODER.raw_decode(page, match.end())
    except ValueError:
        return None
    return value


def html_to_text(fragment: str | None) -> str:
    """Readable plain text from a job description's HTML (lists become ``- `` lines)."""
    if not fragment:
        return ""
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", "", fragment)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)<li\b[^>]*>", "\n- ", text)
    text = re.sub(r"(?i)</?(?:p|div|h[1-6]|ul|ol|tr|table|section)\b[^>]*>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text).replace("\xa0", " ")
    lines: list[str] = []
    for raw in text.splitlines():
        line = " ".join(raw.split())
        if line or (lines and lines[-1]):
            lines.append(line)
    return "\n".join(lines).strip()


def _text(value: Any) -> str | None:
    """A label that may be a plain string or ``{"text": ...}``."""
    if isinstance(value, dict):
        value = value.get("text")
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _id(value: Any) -> str | None:
    if value in (None, "", 0, "0"):
        return None
    return str(value)


# -- search ----------------------------------------------------------------------------


def parse_card(card: dict[str, Any], market: Market) -> Job:
    """One job from a search response."""
    job_id = str(card["id"])
    advertiser = card.get("advertiser") or {}
    locations = [loc for loc in card.get("locations") or [] if isinstance(loc, dict)]
    first = locations[0] if locations else {}
    classes = (card.get("classifications") or [{}])[0] or {}
    top = classes.get("classification") or {}
    sub = classes.get("subclassification") or {}
    arrangements = (card.get("workArrangements") or {}).get("data") or []
    label = (card.get("salaryLabel") or "").strip() or None
    currency = card.get("currencyLabel") or market.currency
    salary = parse_salary(label, currency)
    return Job(
        job_id=job_id,
        title=(card.get("title") or "").strip(),
        url=f"{market.base_url}/job/{job_id}",
        market=market.code,
        company=(card.get("companyName") or advertiser.get("description") or None),
        advertiser_id=_id(advertiser.get("id")),
        private_advertiser=not advertiser.get("id"),
        company_profile_id=_id(card.get("companyProfileStructuredDataId")),
        location=first.get("label"),
        locations=[loc["label"] for loc in locations if loc.get("label")],
        location_hierarchy=[
            h["contextualName"] for h in first.get("seoHierarchy") or [] if h.get("contextualName")
        ],
        country_code=first.get("countryCode"),
        classification=top.get("description"),
        classification_id=_id(top.get("id")),
        subclassification=sub.get("description"),
        subclassification_id=_id(sub.get("id")),
        work_types=[str(w) for w in card.get("workTypes") or []],
        work_arrangements=[
            t for t in (_text((a or {}).get("label")) for a in arrangements) if t is not None
        ],
        salary_label=label,
        salary_min=salary.min,
        salary_max=salary.max,
        salary_period=salary.period,
        salary_currency=salary.currency,
        teaser=(card.get("teaser") or "").strip() or None,
        bullet_points=[b.strip() for b in card.get("bulletPoints") or [] if b and b.strip()],
        badges=[
            t["label"] for t in card.get("tags") or [] if isinstance(t, dict) and t.get("label")
        ],
        is_featured=bool(card.get("isFeatured")),
        listed_at=card.get("listingDate"),
        listed_ago=card.get("listingDateDisplay"),
        logo_url=(card.get("branding") or {}).get("serpLogoUrl"),
        role_id=card.get("roleId"),
    )


def _search_data(body: Any) -> dict[str, Any]:
    data = unwrap_json(body)
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        raise ValueError("not a SEEK search response")
    return data


def parse_search(body: Any, market: Market, page: int, page_size: int, url: str) -> SearchPage:
    """One page of search results."""
    data = _search_data(body)
    location = data.get("location") or {}
    sort = next((m.get("value") for m in data.get("sortModes") or [] if m.get("isActive")), None)
    return SearchPage(
        market=market.code,
        page=page,
        page_size=page_size,
        total=int(data.get("totalCount") or 0),
        jobs=[parse_card(card, market) for card in data["data"] if card.get("id")],
        location=location.get("description"),
        location_id=_id(location.get("whereId")),
        sort=sort,
        url=url,
    )


def _counts(rows: Any) -> list[dict[str, Any]]:
    out = []
    for row in rows or []:
        out.append(
            {"id": str(row.get("id")), "label": _text(row.get("label")), "count": row.get("count")}
        )
    return out


def parse_facets(body: Any, market: Market, keywords: str | None, where: str | None) -> Facets:
    """Job counts by work type, work arrangement and salary floor for one search."""
    data = _search_data(body)
    facets = data.get("facets") or {}
    salary = []
    for row in facets.get("salaryMin") or []:
        try:
            amount = int(float(row.get("id")))
        except (TypeError, ValueError):
            continue
        salary.append({"amount": amount, "count": row.get("count")})
    salary.sort(key=lambda r: r["amount"])
    related = [
        {"keywords": r.get("keywords"), "total_jobs": r.get("totalJobs")}
        for r in (data.get("suggestions") or {}).get("relatedSearches") or []
        if r.get("keywords")
    ]
    return Facets(
        market=market.code,
        keywords=keywords,
        where=where,
        location=(data.get("location") or {}).get("description"),
        total=int(data.get("totalCount") or 0),
        work_types=_counts(facets.get("workType")),
        work_arrangements=_counts(facets.get("workArrangement")),
        salary_at_least=salary,
        related_searches=related,
    )


# -- job pages -------------------------------------------------------------------------


def _when(value: Any) -> str | None:
    return (value or {}).get("dateTimeUtc") if isinstance(value, dict) else None


def parse_company(profile: dict[str, Any] | None, fallback_url: str | None) -> Company | None:
    if not profile:
        return None
    overview = profile.get("overview") or {}
    paragraphs = ((overview.get("description") or {}).get("paragraphs")) or []
    reviews = (profile.get("reviewsSummary") or {}).get("overallRating") or {}
    count = (reviews.get("numberOfReviews") or {}).get("value")
    return Company(
        id=_id(profile.get("id")),
        name=profile.get("name"),
        slug=profile.get("companyNameSlug"),
        url=fallback_url,
        industry=overview.get("industry"),
        size=(overview.get("size") or {}).get("description"),
        website=(overview.get("website") or {}).get("url"),
        overview="\n\n".join(p.strip() for p in paragraphs if p and p.strip()) or None,
        rating=reviews.get("value"),
        reviews_count=count,
        perks=[p["title"] for p in profile.get("perksAndBenefits") or [] if p.get("title")],
        logo_url=(profile.get("branding") or {}).get("logo"),
    )


def parse_job_page(page: str, market: Market, job_id: str) -> JobDetails:
    """Full job details from a ``/job/<id>`` page."""
    state = window_json(page, "SEEK_REDUX_DATA")
    if not isinstance(state, dict):
        raise ValueError("no job data in the page")
    details = state.get("jobdetails") or {}
    result = details.get("result")
    if not result:
        if details.get("error"):
            raise JobNotFoundError(f"{market.name} has no job {job_id}")
        raise ValueError("no job details in the page")
    job = result.get("job") or {}
    if str(job.get("id")) != str(job_id):
        raise ValueError(f"page shows job {job.get('id')!r}, not {job_id!r}")

    tracking = job.get("tracking") or {}
    info = tracking.get("classificationInfo") or {}
    area = (tracking.get("locationInfo") or {}).get("area")
    gfj = result.get("gfjInfo") or {}
    place = gfj.get("location") or {}
    salary_info = job.get("salary") or {}
    label = (salary_info.get("label") or "").strip() or None
    currency = salary_info.get("currencyLabel") or market.currency
    salary = parse_salary(label, currency)
    products = job.get("products") or {}
    branding = products.get("branding") or {}
    advertiser = job.get("advertiser") or {}
    arrangements = (result.get("workArrangements") or {}).get("arrangements") or []
    content = job.get("content") or ""
    company_url = (gfj.get("company") or {}).get("url")
    return JobDetails(
        job_id=str(job["id"]),
        title=(job.get("title") or "").strip(),
        url=f"{market.base_url}/job/{job['id']}",
        market=market.code,
        status=job.get("status"),
        is_expired=bool(job.get("isExpired")),
        listed_at=_when(job.get("listedAt")),
        expires_at=_when(job.get("expiresAt")),
        company=((result.get("companyProfile") or {}).get("name") or advertiser.get("name")),
        advertiser_id=_id(advertiser.get("id")),
        advertiser_name=advertiser.get("name"),
        advertiser_verified=advertiser.get("isVerified"),
        advertiser_registered_at=_when(advertiser.get("registrationDate")),
        private_advertiser=bool(tracking.get("isPrivateAdvertiser")),
        location=(job.get("location") or {}).get("label"),
        area=area,
        suburb=place.get("suburb"),
        region=place.get("region"),
        state=place.get("state"),
        postcode=place.get("postcode"),
        country=place.get("country"),
        country_code=place.get("countryCode"),
        classification=info.get("classification"),
        classification_id=_id(info.get("classificationId")),
        subclassification=info.get("subClassification"),
        subclassification_id=_id(info.get("subClassificationId")),
        work_type=(job.get("workTypes") or {}).get("label"),
        work_arrangements=[a["label"] for a in arrangements if a.get("label")],
        salary_label=label,
        salary_min=salary.min,
        salary_max=salary.max,
        salary_period=salary.period,
        salary_currency=salary.currency,
        abstract=(job.get("abstract") or "").strip() or None,
        bullet_points=[b.strip() for b in products.get("bullets") or [] if b and b.strip()],
        description_html=content,
        description_text=html_to_text(content),
        questions=list((products.get("questionnaire") or {}).get("questions") or []),
        video_url=(products.get("video") or {}).get("url"),
        logo_url=(branding.get("logo") or {}).get("url"),
        cover_image_url=(branding.get("cover") or {}).get("url"),
        applies_on_employer_site=bool(job.get("isLinkOut")),
        is_verified=job.get("isVerified"),
        role=(result.get("seoInfo") or {}).get("normalisedRoleTitle"),
        company_jobs_url=result.get("companySearchUrl"),
        company_profile=parse_company(result.get("companyProfile"), company_url),
    )
