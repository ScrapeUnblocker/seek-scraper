from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import pytest

from seek_scraper import InputError, SearchFilters, get_market, job_url, parse_job_ref, search_url
from seek_scraper.markets import MARKETS, classification_id, market_for_host


def params(url: str) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}


def test_plain_search_url():
    url = search_url("au", "data engineer", "All Sydney NSW")
    assert url.startswith("https://www.seek.com.au/api/jobsearch/v5/search?")
    assert params(url) == {
        "siteKey": "AU-Main",
        "locale": "en-AU",
        "keywords": "data engineer",
        "where": "All Sydney NSW",
        "page": "1",
        "pageSize": "100",
    }


def test_every_filter_maps_to_the_site_parameter():
    filters = SearchFilters(
        classifications=["it", "1203"],
        subclassifications=["6287"],
        work_types=["full-time", "contract"],
        work_arrangements=["hybrid", "remote"],
        salary_min=100_000,
        salary_max=150_000,
        salary_type="annual",
        listed_within_days=7,
        sort="date",
    )
    p = params(search_url("au", "nurse", filters=filters, page=3, page_size=22))
    assert p["classification"] == "6281,1203"
    assert p["subclassification"] == "6287"
    assert p["worktype"] == "242,244"
    assert p["workarrangement"] == "2,3"
    assert p["salaryrange"] == "100000-150000"
    assert p["salarytype"] == "annual"
    assert p["daterange"] == "7"
    assert p["sortmode"] == "ListedDate"
    assert (p["page"], p["pageSize"]) == ("3", "22")


def test_open_salary_ranges():
    assert params(search_url("au", filters=SearchFilters(salary_min=90000)))["salaryrange"] == (
        "90000-"
    )
    assert params(search_url("au", filters=SearchFilters(salary_max=60000)))["salaryrange"] == (
        "0-60000"
    )


def test_relevance_sort_is_the_default_and_not_sent():
    assert "sortmode" not in params(search_url("au", "x"))


def test_facets_url_asks_for_counts():
    p = params(search_url("sg", "analyst", facets=True, page_size=1))
    assert p["facets"] == "salaryMin,workArrangement,workType"
    assert p["include"] == "relatedsearches"
    assert p["siteKey"] == "SG-Main"


@pytest.mark.parametrize(
    "filters",
    [
        SearchFilters(salary_min=100, salary_max=50),
        SearchFilters(salary_min=-1),
        SearchFilters(salary_type="weekly"),
        SearchFilters(listed_within_days=2),
        SearchFilters(sort="newest"),
        SearchFilters(work_types=["freelance"]),
        SearchFilters(work_arrangements=["moon"]),
        SearchFilters(classifications=["not-a-thing"]),
        SearchFilters(subclassifications=["developers"]),
    ],
)
def test_bad_filters_are_rejected(filters):
    with pytest.raises(InputError):
        search_url("au", "x", filters=filters)


@pytest.mark.parametrize("page_size", [0, 101])
def test_page_size_bounds(page_size):
    with pytest.raises(InputError):
        search_url("au", "x", page_size=page_size)


def test_markets_cover_seek_jobstreet_and_jobsdb():
    assert set(MARKETS) == {"au", "nz", "my", "sg", "ph", "id", "hk", "th"}
    assert get_market("HK").host == "hk.jobsdb.com"
    assert get_market("id").site_key == "ID-Main"
    with pytest.raises(InputError):
        get_market("uk")


@pytest.mark.parametrize(
    ("host", "code"),
    [
        ("www.seek.com.au", "au"),
        ("seek.com.au", "au"),
        ("au.seek.com", "au"),
        ("www.seek.co.nz", "nz"),
        ("my.jobstreet.com", "my"),
        ("PH.JOBSTREET.COM", "ph"),
        ("th.jobsdb.com", "th"),
    ],
)
def test_market_for_host(host, code):
    assert market_for_host(host).code == code


def test_unknown_host():
    assert market_for_host("www.example.com") is None


@pytest.mark.parametrize(
    ("ref", "code", "job_id"),
    [
        ("90000001", "nz", "90000001"),
        (90000001, "nz", "90000001"),
        ("https://www.seek.com.au/job/90000001", "au", "90000001"),
        ("https://au.seek.com/job/90000001?tracking=SHR-WEB", "au", "90000001"),
        ("https://my.jobstreet.com/job/90000002?type=standard", "my", "90000002"),
        ("hk.jobsdb.com/job/90000003", "hk", "90000003"),
        (
            "https://www.seek.com.au/data-engineer-jobs?jobId=90000004&type=standard",
            "au",
            "90000004",
        ),
    ],
)
def test_parse_job_ref(ref, code, job_id):
    market, found = parse_job_ref(ref, "nz")
    assert (market.code, found) == (code, job_id)


@pytest.mark.parametrize(
    "ref", ["", "abc", "https://www.example.com/job/1", "https://www.seek.com.au/"]
)
def test_parse_job_ref_rejects_junk(ref):
    with pytest.raises(InputError):
        parse_job_ref(ref)


def test_job_url():
    assert job_url("th", 1) == "https://th.jobsdb.com/job/1"


@pytest.mark.parametrize(
    ("value", "cid"),
    [
        ("6281", "6281"),
        ("information-communication-technology", "6281"),
        ("Information & Communication Technology", "6281"),
        ("IT", "6281"),
        ("healthcare", "1211"),
        ("hr", "6317"),
        ("accounting", "1200"),
        ("mining", "6058"),
        ("sport", "6246"),
    ],
)
def test_classification_id(value, cid):
    assert classification_id(value) == cid


def test_ambiguous_classification_prefix_is_rejected():
    with pytest.raises(InputError):
        classification_id("c")  # call centre, CEO, community, construction, consulting
