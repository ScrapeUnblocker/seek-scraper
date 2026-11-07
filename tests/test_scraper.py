from __future__ import annotations

import json
from urllib.parse import parse_qs, urlsplit

import pytest
from conftest import (
    SYDNEY,
    BlockedError,
    TargetNotFoundError,
    card,
    job_page,
    job_result,
    search_body,
)

from seek_scraper import JobNotFoundError, ParseError, SearchFilters, SeekError


def query(url: str) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}


def cards(start: int, count: int) -> list[dict]:
    return [card(str(start + i)) for i in range(count)]


def test_search_one_page(make_scraper):
    scraper, client, _ = make_scraper(search_body(cards(1, 3), total=3, location=SYDNEY))
    page = scraper.search("data engineer", "Sydney", SearchFilters(work_arrangements=["remote"]))
    assert [j.job_id for j in page.jobs] == ["1", "2", "3"]
    assert page.location == "All Sydney NSW"
    assert page.jobs[0].search_keywords == "data engineer"
    assert page.jobs[0].search_where == "Sydney"
    url, kwargs = client.calls[0]
    assert url.startswith("https://www.seek.com.au/api/jobsearch/v5/search?")
    assert query(url)["workarrangement"] == "3"
    assert kwargs == {}  # search is not routed by default
    assert scraper.requests == 1


def test_search_other_market_and_wrapped_json(make_scraper):
    scraper, client, _ = make_scraper(search_body(cards(1, 2), wrapped=True))
    page = scraper.search("admin", "Jakarta Raya", market="id")
    assert len(page.jobs) == 2
    assert page.jobs[0].url == "https://id.jobstreet.com/job/1"
    assert page.jobs[0].salary_currency == "IDR"
    assert query(client.calls[0][0])["siteKey"] == "ID-Main"


def test_unknown_location_is_logged(make_scraper, caplog):
    scraper, _, _ = make_scraper(search_body([], total=0))
    with caplog.at_level("WARNING"):
        page = scraper.search("python", "Xyzzyville")
    assert page.jobs == []
    assert "did not recognise the location" in caplog.text


def test_search_jobs_reads_pages_until_the_limit(make_scraper):
    scraper, client, _ = make_scraper(
        search_body(cards(1, 100), total=250),
        search_body(cards(101, 100), total=250),
        search_body(cards(201, 50), total=250),
    )
    jobs = scraper.search_jobs("nurse", limit=None)
    assert len(jobs) == 250
    assert [query(u)["page"] for u, _ in client.calls] == ["1", "2", "3"]


def test_small_limit_uses_a_small_page(make_scraper):
    scraper, client, _ = make_scraper(search_body(cards(1, 20), total=900))
    jobs = scraper.search_jobs("nurse", limit=20)
    assert len(jobs) == 20
    assert query(client.calls[0][0])["pageSize"] == "20"


def test_limit_cuts_the_last_page(make_scraper):
    scraper, client, _ = make_scraper(
        search_body(cards(1, 100), total=900), search_body(cards(101, 100), total=900)
    )
    assert len(scraper.search_jobs("nurse", limit=150)) == 150
    assert len(client.calls) == 2


def test_paging_stops_at_the_result_cap(make_scraper):
    pages = [search_body(cards(i * 100 + 1, 100), total=8000) for i in range(5)]
    scraper, client, _ = make_scraper(*pages)
    assert len(scraper.search_jobs("nurse", limit=None)) == 500
    assert len(client.calls) == 5


def test_bad_limit(make_scraper):
    scraper, _, _ = make_scraper()
    with pytest.raises(ValueError):
        scraper.search_jobs("x", limit=0)


def test_collect_merges_searches_and_dedupes(make_scraper):
    answers = {
        ("data engineer", "Sydney"): ["1", "2"],
        ("data engineer", "Melbourne"): ["2", "3"],
        ("analytics engineer", "Sydney"): ["3", "4"],
        ("analytics engineer", "Melbourne"): ["5"],
    }

    def respond(url, kwargs):
        q = query(url)
        ids = answers[(q["keywords"], q["where"])]
        return search_body([card(i) for i in ids])

    scraper, client, _ = make_scraper(responder=respond)
    jobs = scraper.collect(["data engineer", "analytics engineer"], ["Sydney", "Melbourne"])
    assert [j.job_id for j in jobs] == ["1", "2", "3", "4", "5"]
    assert jobs[2].search_keywords == "data engineer" and jobs[2].search_where == "Melbourne"
    assert len(client.calls) == 4


def test_facets_is_one_small_request(make_scraper):
    body = search_body(
        [card()], total=40, facets={"workType": [{"id": "243", "count": 9, "label": "Part Time"}]}
    )
    scraper, client, _ = make_scraper(body)
    facets = scraper.facets("barista", "Perth", market="au")
    assert facets.total == 40
    assert facets.work_types[0]["label"] == "Part Time"
    q = query(client.calls[0][0])
    assert q["pageSize"] == "1" and "facets" in q


def test_job_details_route_through_the_market_country(make_scraper):
    scraper, client, _ = make_scraper(job_page(job_result()))
    job = scraper.job("https://my.jobstreet.com/job/90000001")
    assert job.market == "my"
    assert job.url == "https://my.jobstreet.com/job/90000001"
    assert job.salary_currency == "MYR"
    url, kwargs = client.calls[0]
    assert url == "https://my.jobstreet.com/job/90000001"
    assert kwargs == {"proxy_country": "my"}


def test_country_override_applies_to_everything(make_scraper):
    scraper, client, _ = make_scraper(search_body([card()]), job_page(job_result()), country="SG")
    scraper.search("x")
    scraper.job("90000001")
    assert [kw for _, kw in client.calls] == [{"proxy_country": "sg"}] * 2


def test_unknown_job_raises_not_found(make_scraper):
    scraper, client, _ = make_scraper(TargetNotFoundError("404"))
    with pytest.raises(JobNotFoundError):
        scraper.job("1")
    assert len(client.calls) == 1  # a 404 is not retried


def test_jobs_skips_missing(make_scraper):
    scraper, _, _ = make_scraper(TargetNotFoundError("404"), job_page(job_result()))
    found = list(scraper.jobs(["1", "90000001"]))
    assert [j.job_id for j in found] == ["90000001"]


def test_jobs_can_raise_on_missing(make_scraper):
    scraper, _, _ = make_scraper(TargetNotFoundError("404"))
    with pytest.raises(JobNotFoundError):
        list(scraper.jobs(["1"], skip_missing=False))


def test_transient_errors_are_retried_with_backoff(make_scraper):
    scraper, client, sleeps = make_scraper(
        BlockedError("blocked"), BlockedError("blocked"), search_body([card()]), backoff=1.5
    )
    page = scraper.search("x")
    assert len(page.jobs) == 1
    assert sleeps == [1.5, 3.0]
    assert scraper.requests == 3


def test_retries_give_up(make_scraper):
    scraper, _, sleeps = make_scraper(*[BlockedError("blocked")] * 3, max_retries=2)
    with pytest.raises(BlockedError):
        scraper.search("x")
    assert len(sleeps) == 2


def test_other_errors_are_not_retried(make_scraper):
    scraper, client, _ = make_scraper(KeyError("boom"))
    with pytest.raises(KeyError):
        scraper.search("x")
    assert len(client.calls) == 1


def test_a_bad_answer_is_fetched_once_more(make_scraper):
    scraper, client, sleeps = make_scraper("<html>Just a moment</html>", search_body([card()]))
    assert len(scraper.search("x").jobs) == 1
    assert len(client.calls) == 2


def test_two_bad_answers_raise_parse_error(make_scraper):
    scraper, _, _ = make_scraper(json.dumps({"oops": 1}), json.dumps({"oops": 1}))
    with pytest.raises(ParseError):
        scraper.search("x")


def test_search_api_404_is_a_seek_error(make_scraper):
    scraper, _, _ = make_scraper(TargetNotFoundError("404"))
    with pytest.raises(SeekError):
        scraper.search("x")


def test_watch_reports_only_new_jobs(make_scraper, tmp_path):
    state = tmp_path / "state.json"
    scraper, client, _ = make_scraper(
        search_body([card("1"), card("2")]),
        search_body([card("3"), card("1"), card("2")]),
    )
    first = scraper.watch(str(state), ["nurse"])
    assert [j.job_id for j in first] == ["1", "2"]  # the baseline
    assert query(client.calls[0][0])["sortmode"] == "ListedDate"
    second = scraper.watch(str(state), ["nurse"])
    assert [j.job_id for j in second] == ["3"]
    saved = json.loads(state.read_text(encoding="utf-8"))["seen"]
    assert sorted(saved) == ["1", "2", "3"]
