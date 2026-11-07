"""Offline fixtures: small SEEK responses built from the shapes of real ones, and a fake SDK.

Nothing here talks to the network or spends API credit.
"""

from __future__ import annotations

import copy
import html
import json
from typing import Any, Callable

import pytest

from seek_scraper import SeekScraper

# -- search API --------------------------------------------------------------------------


def card(job_id: str = "90000001", **extra: Any) -> dict[str, Any]:
    data = {
        "advertiser": {"id": "40000001", "description": "Example Recruitment"},
        "bulletPoints": ["Hybrid - 3 days in the office", "Modern data stack"],
        "branding": {"serpLogoUrl": "https://images.example.com/logo.png"},
        "classifications": [
            {
                "classification": {
                    "id": "6281",
                    "description": "Information & Communication Technology",
                },
                "subclassification": {"id": "6287", "description": "Developers/Programmers"},
            }
        ],
        "companyName": "Example Analytics",
        "companyProfileStructuredDataId": 123456,
        "displayType": "standard",
        "employer": {"id": "123456", "name": "Example Analytics"},
        "id": job_id,
        "isFeatured": False,
        "listingDate": "2026-11-06T04:45:58Z",
        "listingDateDisplay": "1d ago",
        "locations": [
            {
                "label": "Sydney NSW",
                "countryCode": "AU",
                "seoHierarchy": [
                    {"contextualName": "All Sydney NSW"},
                    {"contextualName": "New South Wales NSW"},
                ],
            }
        ],
        "roleId": "data-engineer",
        "salaryLabel": "$120,000 \u2013 $140,000 per year + super",
        "teaser": "Build and run data pipelines.",
        "title": "Data Engineer",
        "workTypes": ["Full time"],
        "workArrangements": {"data": [{"id": "2", "label": {"text": "Hybrid"}}]},
        "tags": [{"type": "EARLY_APPLICANT", "label": "Be an early applicant"}],
    }
    data.update(extra)
    return data


def search_body(
    cards: list[dict[str, Any]],
    *,
    total: int | None = None,
    location: dict[str, Any] | None = None,
    facets: dict[str, Any] | None = None,
    suggestions: dict[str, Any] | None = None,
    wrapped: bool = False,
) -> str:
    data: dict[str, Any] = {
        "data": cards,
        "totalCount": len(cards) if total is None else total,
        "sortModes": [
            {"isActive": True, "name": "Relevance", "value": "KeywordRelevance"},
            {"isActive": False, "name": "Date", "value": "ListedDate"},
        ],
        "facets": facets or {},
        "searchParams": {"sitekey": "AU-Main"},
    }
    if location is not None:
        data["location"] = location
    if suggestions is not None:
        data["suggestions"] = suggestions
    text = json.dumps(data, ensure_ascii=False)
    if not wrapped:
        return text
    # The browser's plain-text view of a JSON response, HTML-escaped inside <pre>.
    return (
        '<html><head><meta name="color-scheme" content="light dark"></head>'
        f"<body><pre>{html.escape(text, quote=False)}</pre>"
        '<div class="json-formatter-container"></div></body></html>'
    )


SYDNEY = {"description": "All Sydney NSW", "whereId": "1000", "type": "Location"}

# -- job pages ---------------------------------------------------------------------------

JOB_RESULT: dict[str, Any] = {
    "gfjInfo": {
        "location": {
            "countryCode": "AU",
            "country": "Australia",
            "suburb": "Sydney",
            "region": None,
            "state": "New South Wales",
            "postcode": "2000",
        },
        "workTypes": {"label": ["FULL_TIME"]},
        "company": {"url": "https://au.seek.com/companies/example-analytics-123456"},
    },
    "workArrangements": {"arrangements": [{"type": "HYBRID", "label": "Hybrid"}]},
    "seoInfo": {"normalisedRoleTitle": "Data Engineer"},
    "job": {
        "id": "90000001",
        "title": "Data Engineer",
        "tracking": {
            "classificationInfo": {
                "classificationId": "6281",
                "classification": "Information & Communication Technology",
                "subClassificationId": "6287",
                "subClassification": "Developers/Programmers",
            },
            "isPrivateAdvertiser": False,
            "locationInfo": {"area": "CBD, Inner West & Eastern Suburbs", "location": "Sydney"},
        },
        "isExpired": False,
        "expiresAt": {"dateTimeUtc": "2026-12-06T12:59:59.999Z"},
        "isLinkOut": True,
        "isVerified": True,
        "abstract": "Build and run data pipelines.",
        "content": (
            "<p>Join our <b>data</b> team.</p><ul><li>Python &amp; SQL</li><li>dbt</li></ul>"
        ),
        "status": "Active",
        "listedAt": {"label": "1d ago", "dateTimeUtc": "2026-11-06T04:45:58.631Z"},
        "salary": {"currencyLabel": None, "label": "$120,000 \u2013 $140,000 per year + super"},
        "workTypes": {"label": "Full time"},
        "advertiser": {
            "id": "40000001",
            "name": "Example Analytics",
            "isVerified": True,
            "registrationDate": {"dateTimeUtc": "2015-03-01T00:00:00.000Z"},
        },
        "location": {"label": "Sydney NSW"},
        "products": {
            "branding": {
                "cover": {"url": "https://images.example.com/cover.jpg"},
                "logo": {"url": "https://images.example.com/logo.png"},
            },
            "bullets": ["Hybrid", "Modern stack"],
            "questionnaire": {"questions": ["How many years' experience do you have with dbt?"]},
            "video": {"url": "https://www.youtube.com/embed/example", "position": "BOTTOM"},
        },
    },
    "companyProfile": {
        "id": "123456",
        "name": "Example Analytics",
        "companyNameSlug": "example-analytics-123456",
        "branding": {"logo": "https://images.example.com/company.png"},
        "overview": {
            "description": {"paragraphs": ["We build analytics.", "Offices in Sydney."]},
            "industry": "Software",
            "size": {"description": "101-1,000 employees"},
            "website": {"url": "https://www.example.com"},
        },
        "reviewsSummary": {"overallRating": {"numberOfReviews": {"value": 87}, "value": 4.1}},
        "perksAndBenefits": [{"title": "Flexible working"}, {"title": "Learning budget"}],
    },
    "companySearchUrl": "https://au.seek.com/Example-Analytics-jobs/at-this-company",
}


def job_result(**job_overrides: Any) -> dict[str, Any]:
    result = copy.deepcopy(JOB_RESULT)
    result["job"].update(job_overrides)
    return result


def job_page(result: dict[str, Any] | None = None, *, error: bool = False) -> str:
    state = {
        "jobdetails": {"jobPending": False, "result": result, "error": error},
        "search": {},
    }
    return (
        "<!DOCTYPE html><html><head><title>Data Engineer Job in Sydney - SEEK</title></head><body>"
        '<div id="app"></div>'
        '<script>window.SEEK_CONFIG = {"brand": "seek"};\n'
        f"window.SEEK_REDUX_DATA = {json.dumps(state)};\n"
        'window.SK_DL = {"siteSection": "discover"};</script></body></html>'
    )


# -- a fake SDK ----------------------------------------------------------------------------


class BlockedError(Exception):
    """Named like the SDK's exception; the scraper matches errors by class name."""


class TargetNotFoundError(Exception):
    pass


class FakeClient:
    """Stands in for ``scrapeunblocker.Client``.

    ``responder(url, kwargs)`` returns a body or raises; each call is recorded.
    """

    def __init__(self, responder: Callable[[str, dict[str, Any]], Any]):
        self.responder = responder
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get_page_source(self, url: str, **kwargs: Any) -> Any:
        self.calls.append((url, kwargs))
        return self.responder(url, kwargs)


def queue(*answers: Any) -> Callable[[str, dict[str, Any]], Any]:
    """A responder that plays ``answers`` in order (exceptions are raised)."""
    items = list(answers)

    def respond(url: str, kwargs: dict[str, Any]) -> Any:
        if not items:
            raise AssertionError(f"unexpected request: {url}")
        answer = items.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return answer

    return respond


@pytest.fixture
def make_scraper() -> Callable[..., tuple[SeekScraper, FakeClient, list[float]]]:
    def build(*answers: Any, responder: Any = None, **kwargs: Any):
        client = FakeClient(responder or queue(*answers))
        sleeps: list[float] = []
        scraper = SeekScraper(client=client, sleep=sleeps.append, **kwargs)
        return scraper, client, sleeps

    return build
