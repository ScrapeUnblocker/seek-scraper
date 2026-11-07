from __future__ import annotations

import json

import pytest
from conftest import card, job_page, job_result, search_body

from seek_scraper import cli
from seek_scraper.cli import build_parser, filters_from, main, run


def parse(*argv: str):
    return build_parser().parse_args(list(argv))


def test_search_arguments_become_filters():
    args = parse(
        "search",
        "data engineer",
        "analyst",
        "--where",
        "Sydney",
        "-w",
        "Melbourne",
        "-c",
        "it,banking",
        "--work-type",
        "full-time",
        "--work-type",
        "contract",
        "--remote",
        "--hybrid",
        "--work-arrangement",
        "remote",
        "--salary-min",
        "100000",
        "--salary-type",
        "annual",
        "--listed-within",
        "7",
        "--sort",
        "date",
        "-n",
        "50",
        "--market",
        "NZ",
    )
    assert args.keywords == ["data engineer", "analyst"]
    assert args.where == ["Sydney", "Melbourne"]
    assert args.market == "nz"
    f = filters_from(args)
    assert f.classifications == ["it", "banking"]
    assert f.work_types == ["full-time", "contract"]
    assert f.work_arrangements == ["remote", "hybrid"]
    assert (f.salary_min, f.salary_type, f.listed_within_days, f.sort) == (
        100000,
        "annual",
        7,
        "date",
    )
    assert args.limit == 50


def test_watch_sorts_by_date_by_default():
    args = parse("watch", "nurse", "--state", "s.json")
    assert filters_from(args).sort == "date"


def test_bad_choices_exit():
    with pytest.raises(SystemExit):
        parse("search", "x", "--listed-within", "2")
    with pytest.raises(SystemExit):
        parse("search", "x", "--market", "uk")


def test_format_from_extension():
    assert cli._format(parse("search", "x", "-o", "jobs.csv")) == "csv"
    assert cli._format(parse("search", "x", "-o", "jobs.jsonl")) == "jsonl"
    assert cli._format(parse("search", "x")) == "table"
    assert cli._format(parse("job", "1")) == "json"
    assert cli._format(parse("search", "x", "-o", "jobs.csv", "-f", "json")) == "json"


def test_offline_commands_need_no_key(monkeypatch, capsys):
    monkeypatch.delenv("SCRAPEUNBLOCKER_KEY", raising=False)
    assert main(["classifications", "-f", "json"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert len(rows) == 30 and rows[0] == {"id": "1200", "slug": "accounting", "name": "Accounting"}
    assert main(["markets"]) == 0
    assert "jobsdb.com" in capsys.readouterr().out


def test_network_commands_need_a_key(monkeypatch, capsys):
    monkeypatch.delenv("SCRAPEUNBLOCKER_KEY", raising=False)
    assert main(["search", "x"]) == 2
    assert "SCRAPEUNBLOCKER_KEY" in capsys.readouterr().err


def test_run_search_and_details(make_scraper):
    scraper, client, _ = make_scraper(search_body([card()]), job_page(job_result()))
    result = run(parse("search", "data", "--details"), scraper)
    assert [d.job_id for d in result] == ["90000001"]
    assert result[0].company_profile.rating == 4.1
    assert len(client.calls) == 2


def test_run_single_job_returns_one_record(make_scraper):
    scraper, _, _ = make_scraper(job_page(job_result()))
    result = run(parse("job", "https://www.seek.com.au/job/90000001"), scraper)
    assert result.job_id == "90000001"


def test_run_facets_per_keyword(make_scraper):
    scraper, client, _ = make_scraper(
        search_body([card()], total=5), search_body([card()], total=7)
    )
    result = run(parse("facets", "nurse", "midwife", "-m", "nz"), scraper)
    assert [f.total for f in result] == [5, 7]
    assert [f.keywords for f in result] == ["nurse", "midwife"]


def test_main_writes_csv(monkeypatch, tmp_path, make_scraper, capsys):
    scraper, _, _ = make_scraper(search_body([card("1"), card("2")]))
    monkeypatch.setenv("SCRAPEUNBLOCKER_KEY", "test-key")
    monkeypatch.setattr(cli, "SeekScraper", lambda **kwargs: scraper)
    out = tmp_path / "jobs.csv"
    assert main(["search", "data engineer", "-o", str(out)]) == 0
    text = out.read_text(encoding="utf-8-sig")
    header = text.splitlines()[0].split(",")
    assert header[:3] == ["job_id", "title", "url"]
    assert "Hybrid - 3 days in the office; Modern data stack" in text
    assert "wrote 2 record(s)" in capsys.readouterr().err


def test_main_reports_input_errors(monkeypatch, make_scraper, capsys):
    scraper, _, _ = make_scraper()
    monkeypatch.setenv("SCRAPEUNBLOCKER_KEY", "test-key")
    monkeypatch.setattr(cli, "SeekScraper", lambda **kwargs: scraper)
    assert main(["search", "x", "-c", "astrology"]) == 2
    assert "unknown classification" in capsys.readouterr().err


def test_main_reports_sdk_errors(monkeypatch, make_scraper, capsys):
    class AuthenticationError(Exception):
        pass

    scraper, _, _ = make_scraper(AuthenticationError("invalid key"))
    monkeypatch.setenv("SCRAPEUNBLOCKER_KEY", "test-key")
    monkeypatch.setattr(cli, "SeekScraper", lambda **kwargs: scraper)
    assert main(["search", "x"]) == 1
    assert "AuthenticationError: invalid key" in capsys.readouterr().err
