from __future__ import annotations

from conftest import card, job_page, job_result

from seek_scraper import Facets, SearchPage, get_market
from seek_scraper.models import salary_text
from seek_scraper.parsing import parse_card, parse_job_page

AU = get_market("au")


def page(n: int, size: int, total: int, count: int | None = None) -> SearchPage:
    jobs = [parse_card(card(str(i)), AU) for i in range(size if count is None else count)]
    return SearchPage(market="au", page=n, page_size=size, total=total, jobs=jobs)


def test_has_next_follows_the_total():
    assert page(1, 10, 25).has_next is True
    assert page(2, 10, 25).has_next is True
    assert page(3, 10, 25, count=5).has_next is False
    assert page(1, 10, 10).has_next is False


def test_has_next_stops_at_seeks_result_cap():
    assert page(4, 100, 8000).has_next is True  # page 5 ends at job 500
    assert page(5, 100, 8000).has_next is False  # page 6 would pass 550
    assert page(24, 22, 8000).has_next is True  # page 25 ends at job 550
    assert page(25, 22, 8000).has_next is False


def test_short_page_has_no_next():
    assert page(1, 100, 900, count=40).has_next is False


def test_salary_text():
    assert salary_text(120000, 140000, "year", "AUD") == "AUD 120,000-140,000/yr"
    assert salary_text(35, 35, "hour", "AUD") == "AUD 35/hr"
    assert salary_text(70000, None, None, "NZD") == "NZD 70,000+"
    assert salary_text(None, 85000, "year", None) == "up to 85,000/yr"
    assert salary_text(1234.5, 1234.5, "week", "SGD") == "SGD 1,234.50/wk"
    assert salary_text(None, None, "year", "AUD") == ""


def test_job_table_row_falls_back_to_the_label():
    job = parse_card(card(salaryLabel="Competitive + bonus"), AU)
    row = job.table_row()
    assert row[0] == "90000001" and row[1] == "2026-11-06"
    assert row[-1] == "Competitive + bonus"
    assert row[-2] == "Full time, Hybrid"


def test_job_details_csv_row_flattens_the_company():
    details = parse_job_page(job_page(job_result()), AU, "90000001")
    row = details.to_row()
    assert "description_html" not in row and "company_profile" not in row
    assert row["company_rating"] == 4.1
    assert row["company_reviews_count"] == 87
    assert row["company_perks"] == ["Flexible working", "Learning budget"]
    assert details.table_row()[-1] == "4.1 (87 reviews)"


def test_facet_rows():
    facets = Facets(
        market="au",
        keywords="nurse",
        where=None,
        location="All Melbourne VIC",
        total=1292,
        work_types=[{"id": "242", "label": "Full Time", "count": 558}],
        salary_at_least=[{"amount": 100000, "count": 886}],
        related_searches=[{"keywords": "registered nurse", "total_jobs": 1805}],
    )
    rows = facets.csv_rows()
    assert [r["facet"] for r in rows] == ["total", "work_type", "salary_at_least", "related_search"]
    assert facets.table_rows()[2] == ("salary_at_least", "AUD 100,000", "886")
