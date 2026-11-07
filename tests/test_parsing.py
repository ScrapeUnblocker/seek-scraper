from __future__ import annotations

import json

import pytest
from conftest import SYDNEY, card, job_page, job_result, search_body

from seek_scraper import JobNotFoundError, get_market
from seek_scraper.parsing import (
    html_to_text,
    parse_card,
    parse_facets,
    parse_job_page,
    parse_search,
    unwrap_json,
    window_json,
)

AU = get_market("au")


def test_unwrap_raw_json():
    assert unwrap_json('  {"data": []}') == {"data": []}


def test_unwrap_json_shown_in_a_pre_block():
    body = search_body([card(companyName="Smith & Sons")], wrapped=True)
    assert "&amp;" in body
    data = unwrap_json(body)
    assert data["data"][0]["companyName"] == "Smith & Sons"


def test_unwrap_rejects_html():
    with pytest.raises(ValueError):
        unwrap_json("<html><body>Access denied</body></html>")


def test_parse_card_fields():
    job = parse_card(card(), AU)
    assert job.job_id == "90000001"
    assert job.url == "https://www.seek.com.au/job/90000001"
    assert job.title == "Data Engineer"
    assert job.company == "Example Analytics"
    assert job.advertiser_id == "40000001"
    assert job.private_advertiser is False
    assert job.company_profile_id == "123456"
    assert job.location == "Sydney NSW"
    assert job.location_hierarchy == ["All Sydney NSW", "New South Wales NSW"]
    assert job.country_code == "AU"
    assert job.classification == "Information & Communication Technology"
    assert (job.classification_id, job.subclassification_id) == ("6281", "6287")
    assert job.work_types == ["Full time"]
    assert job.work_arrangements == ["Hybrid"]
    assert (job.salary_min, job.salary_max, job.salary_period) == (120000, 140000, "year")
    assert job.salary_currency == "AUD"
    assert job.badges == ["Be an early applicant"]
    assert job.bullet_points == ["Hybrid - 3 days in the office", "Modern data stack"]
    assert job.listed_at == "2026-11-06T04:45:58Z"
    assert job.logo_url.endswith("logo.png")


def test_private_advertiser_and_missing_salary():
    raw = card(
        advertiser={"id": "", "description": "Private Advertiser"},
        companyName=None,
        companyProfileStructuredDataId=0,
        salaryLabel="",
        tags=None,
        workArrangements=None,
    )
    job = parse_card(raw, AU)
    assert job.private_advertiser is True
    assert job.company == "Private Advertiser"
    assert job.advertiser_id is None
    assert job.company_profile_id is None
    assert job.salary_label is None
    assert job.salary_min is None and job.salary_currency is None
    assert job.badges == [] and job.work_arrangements == []


def test_card_currency_label_wins_over_market_currency():
    job = parse_card(card(salaryLabel="$5,000 per month", currencyLabel="USD"), get_market("sg"))
    assert job.salary_currency == "USD"
    assert job.url == "https://sg.jobstreet.com/job/90000001"


def test_parse_search_page():
    body = search_body([card("1"), card("2"), {"title": "no id"}], total=841, location=SYDNEY)
    page = parse_search(body, AU, 1, 100, "https://x")
    assert [j.job_id for j in page.jobs] == ["1", "2"]
    assert page.total == 841
    assert page.location == "All Sydney NSW"
    assert page.location_id == "1000"
    assert page.sort == "KeywordRelevance"


def test_parse_search_rejects_other_json():
    with pytest.raises(ValueError):
        parse_search(json.dumps({"error": "nope"}), AU, 1, 100, "https://x")


def test_parse_facets():
    body = search_body(
        [card()],
        total=1292,
        location={"description": "All Melbourne VIC", "whereId": "1002"},
        facets={
            "salaryMin": [
                {"id": "100000", "count": 886, "label": "100000"},
                {"id": "0", "count": 1292, "label": "0"},
                {"id": "oops", "count": 1, "label": "oops"},
            ],
            "workType": [{"id": "242", "count": 558, "label": {"lang": "en", "text": "Full Time"}}],
            "workArrangement": [{"id": "3", "count": 26, "label": {"text": "Remote"}}],
        },
        suggestions={"relatedSearches": [{"keywords": "registered nurse", "totalJobs": 1805}]},
    )
    facets = parse_facets(body, AU, "nurse", "Melbourne")
    assert facets.total == 1292
    assert facets.location == "All Melbourne VIC"
    assert facets.salary_at_least == [
        {"amount": 0, "count": 1292},
        {"amount": 100000, "count": 886},
    ]
    assert facets.work_types == [{"id": "242", "label": "Full Time", "count": 558}]
    assert facets.work_arrangements == [{"id": "3", "label": "Remote", "count": 26}]
    assert facets.related_searches == [{"keywords": "registered nurse", "total_jobs": 1805}]


def test_window_json_reads_one_assignment():
    page = job_page(job_result())
    assert window_json(page, "SK_DL") == {"siteSection": "discover"}
    assert window_json(page, "MISSING") is None


def test_parse_job_page():
    job = parse_job_page(job_page(job_result()), AU, "90000001")
    assert job.title == "Data Engineer"
    assert job.status == "Active" and job.is_expired is False
    assert job.listed_at == "2026-11-06T04:45:58.631Z"
    assert job.expires_at == "2026-12-06T12:59:59.999Z"
    assert job.company == "Example Analytics"
    assert job.advertiser_verified is True
    assert job.advertiser_registered_at.startswith("2015-03-01")
    assert (job.suburb, job.state, job.postcode, job.country) == (
        "Sydney",
        "New South Wales",
        "2000",
        "Australia",
    )
    assert job.area == "CBD, Inner West & Eastern Suburbs"
    assert job.classification_id == "6281" and job.subclassification == "Developers/Programmers"
    assert job.work_type == "Full time"
    assert job.work_arrangements == ["Hybrid"]
    assert (job.salary_min, job.salary_max, job.salary_period) == (120000, 140000, "year")
    assert job.questions == ["How many years' experience do you have with dbt?"]
    assert job.video_url.endswith("/example")
    assert job.applies_on_employer_site is True
    assert job.description_text == "Join our data team.\n\n- Python & SQL\n- dbt"
    assert job.role == "Data Engineer"
    profile = job.company_profile
    assert profile.rating == 4.1 and profile.reviews_count == 87
    assert profile.industry == "Software" and profile.size == "101-1,000 employees"
    assert profile.perks == ["Flexible working", "Learning budget"]
    assert profile.overview == "We build analytics.\n\nOffices in Sydney."
    assert profile.url == "https://au.seek.com/companies/example-analytics-123456"


def test_expired_job_still_parses():
    result = job_result(status="Expired", isExpired=True, salary=None)
    result["companyProfile"] = None
    job = parse_job_page(job_page(result), AU, "90000001")
    assert job.status == "Expired" and job.is_expired is True
    assert job.salary_label is None and job.company_profile is None


def test_job_page_for_another_job_is_a_bad_answer():
    with pytest.raises(ValueError):
        parse_job_page(job_page(job_result()), AU, "90000009")


def test_page_without_job_data_is_a_bad_answer():
    with pytest.raises(ValueError):
        parse_job_page("<html><body>Please wait</body></html>", AU, "1")
    with pytest.raises(ValueError):
        parse_job_page(job_page(None), AU, "1")


def test_page_that_reports_an_error_is_not_found():
    with pytest.raises(JobNotFoundError):
        parse_job_page(job_page(None, error=True), AU, "1")


def test_html_to_text():
    fragment = (
        "<p>Hello&nbsp;there</p><p><br></p><ul><li>One</li><li><b>Two</b></li></ul>"
        "<style>.x{}</style><div>End</div>"
    )
    assert html_to_text(fragment) == "Hello there\n\n- One\n- Two\n\nEnd"
    assert html_to_text(None) == ""
