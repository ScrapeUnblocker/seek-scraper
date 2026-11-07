"""Command-line interface for ``seek-scraper``.

Commands: ``search``, ``job``, ``facets``, ``watch``, ``classifications``, ``markets``.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections.abc import Sequence
from typing import Any

from . import __version__
from .errors import InputError, SeekError
from .export import FORMATS, write
from .markets import CLASSIFICATIONS, LISTED_WITHIN_DAYS, MARKETS, SALARY_TYPES, SORTS
from .scraper import SeekScraper
from .urls import SearchFilters

log = logging.getLogger("seek_scraper")

_EXTENSIONS = {".csv": "csv", ".jsonl": "jsonl", ".json": "json", ".txt": "table"}
_OFFLINE = {"classifications", "markets"}


def _split(values: Sequence[str] | None) -> list[str]:
    """Repeatable options that also accept comma-separated values."""
    return [part.strip() for value in values or () for part in value.split(",") if part.strip()]


def _add_output(parser: argparse.ArgumentParser, *, default_format: str = "table") -> None:
    parser.add_argument(
        "-f",
        "--format",
        choices=FORMATS,
        help=f"output format (default: from the --output extension, else {default_format})",
    )
    parser.set_defaults(default_format=default_format)
    parser.add_argument("-o", "--output", help="write to this file instead of stdout")


def _add_network(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-m",
        "--market",
        default="au",
        type=str.lower,
        choices=list(MARKETS),
        help="site to search: au, nz (SEEK), my, sg, ph, id (Jobstreet), hk, th (JobsDB)",
    )
    parser.add_argument(
        "--country",
        help="two-letter country to route requests through (default: automatic)",
    )
    parser.add_argument(
        "--retries", type=int, default=3, help="extra attempts per request on transient errors"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="log progress to stderr")


def _add_search(parser: argparse.ArgumentParser, *, keywords_help: str) -> None:
    parser.add_argument("keywords", nargs="*", help=keywords_help)
    parser.add_argument(
        "-w",
        "--where",
        action="append",
        metavar="PLACE",
        help='location as typed on the site ("Sydney", "All Melbourne VIC", "Kuala Lumpur"); '
        "repeat for several (default: the whole country)",
    )
    g = parser.add_argument_group("filters")
    g.add_argument(
        "-c",
        "--classification",
        action="append",
        metavar="ID|NAME",
        help="classification id, slug or alias (it, healthcare, hr, ...); repeatable",
    )
    g.add_argument(
        "--subclassification",
        action="append",
        metavar="ID",
        help="subclassification id; repeatable",
    )
    g.add_argument(
        "--work-type",
        action="append",
        metavar="TYPE",
        help="full-time, part-time, contract or casual; repeatable or comma-separated",
    )
    g.add_argument(
        "--work-arrangement",
        action="append",
        metavar="ARR",
        help="on-site, hybrid or remote; repeatable or comma-separated",
    )
    g.add_argument(
        "--remote",
        dest="work_arrangement",
        action="append_const",
        const="remote",
        help="remote only",
    )
    g.add_argument(
        "--hybrid",
        dest="work_arrangement",
        action="append_const",
        const="hybrid",
        help="hybrid only",
    )
    g.add_argument("--salary-min", type=int, metavar="N", help="lowest salary (in --salary-type)")
    g.add_argument("--salary-max", type=int, metavar="N", help="highest salary (in --salary-type)")
    g.add_argument(
        "--salary-type",
        choices=SALARY_TYPES,
        help="period of --salary-min/--salary-max (site default: annual in AU/NZ)",
    )
    g.add_argument(
        "--listed-within",
        type=int,
        choices=LISTED_WITHIN_DAYS,
        metavar="DAYS",
        help=f"only jobs listed in the last N days ({', '.join(map(str, LISTED_WITHIN_DAYS))})",
    )


def _add_sort(parser: argparse.ArgumentParser, default: str) -> None:
    parser.add_argument(
        "--sort", choices=list(SORTS), default=default, help=f"result order (default: {default})"
    )


def _add_limit(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-n",
        "--limit",
        type=int,
        default=100,
        help="jobs per search (default: 100; 100 jobs per request)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="read every page SEEK serves (about 550 jobs per search at most)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="seek-scraper",
        description="Scrape SEEK, Jobstreet and JobsDB jobs as clean JSON or CSV "
        "via the ScrapeUnblocker API.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("search", help="search jobs")
    _add_search(p, keywords_help="keywords; give several to run one search each (merged, deduped)")
    _add_sort(p, "relevance")
    _add_limit(p)
    p.add_argument(
        "--details",
        action="store_true",
        help="also open every job page for full details (one extra request per job)",
    )
    _add_output(p)
    _add_network(p)

    p = sub.add_parser("job", help="full details for job ids or URLs")
    p.add_argument("jobs", nargs="+", help="job id (with --market) or job URL from any site")
    _add_output(p, default_format="json")
    _add_network(p)

    p = sub.add_parser("facets", help="job counts by work type, arrangement and salary")
    _add_search(p, keywords_help="keywords; give several for one count each")
    _add_output(p)
    _add_network(p)

    p = sub.add_parser("watch", help="print jobs that are new since the last run")
    _add_search(p, keywords_help="keywords; give several to watch them together")
    p.add_argument("--state", required=True, help="JSON file that remembers jobs already seen")
    _add_sort(p, "date")
    _add_limit(p)
    _add_output(p)
    _add_network(p)

    p = sub.add_parser("classifications", help="list classification ids and slugs (offline)")
    _add_output(p)

    p = sub.add_parser("markets", help="list the supported sites (offline)")
    _add_output(p)
    return parser


def filters_from(args: argparse.Namespace) -> SearchFilters:
    return SearchFilters(
        classifications=_split(args.classification),
        subclassifications=_split(args.subclassification),
        work_types=_split(args.work_type),
        work_arrangements=list(dict.fromkeys(_split(args.work_arrangement))),
        salary_min=args.salary_min,
        salary_max=args.salary_max,
        salary_type=args.salary_type,
        listed_within_days=args.listed_within,
        sort=getattr(args, "sort", "relevance"),
    )


def _format(args: argparse.Namespace) -> str:
    if args.format:
        return args.format
    if args.output:
        ext = os.path.splitext(args.output)[1].lower()
        if ext in _EXTENSIONS:
            return _EXTENSIONS[ext]
    return args.default_format


def _limit(args: argparse.Namespace) -> int | None:
    if args.all:
        return None
    if args.limit < 1:
        raise InputError("--limit must be 1 or more")
    return args.limit


def _keywords(args: argparse.Namespace) -> list[str | None]:
    return list(args.keywords) or [None]


def _wheres(args: argparse.Namespace) -> list[str | None]:
    return list(args.where or []) or [None]


def run(args: argparse.Namespace, scraper: SeekScraper | None = None) -> Any:
    """Run a parsed command and return what it produced (models or lists of models)."""
    if args.command == "classifications":
        return list(CLASSIFICATIONS)
    if args.command == "markets":
        return list(MARKETS.values())

    if scraper is None:
        scraper = SeekScraper(market=args.market, country=args.country, max_retries=args.retries)

    if args.command == "job":
        if len(args.jobs) == 1:
            return scraper.job(args.jobs[0], market=args.market)
        return list(scraper.jobs(args.jobs, market=args.market))

    filters = filters_from(args)
    if args.command == "facets":
        return [
            scraper.facets(words, where, filters, market=args.market)
            for words in _keywords(args)
            for where in _wheres(args)
        ]
    if args.command == "watch":
        return scraper.watch(
            args.state,
            _keywords(args),
            _wheres(args),
            filters,
            market=args.market,
            limit_per_search=_limit(args),
        )
    jobs = scraper.collect(
        _keywords(args), _wheres(args), filters, market=args.market, limit_per_search=_limit(args)
    )
    if args.details:
        return list(scraper.jobs([job.url for job in jobs]))
    return jobs


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if getattr(args, "verbose", False) else logging.WARNING,
        format="%(levelname)s %(message)s",
        stream=sys.stderr,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if args.command not in _OFFLINE and not os.environ.get("SCRAPEUNBLOCKER_KEY"):
        print(
            "error: set SCRAPEUNBLOCKER_KEY to your ScrapeUnblocker API key (see .env.example)",
            file=sys.stderr,
        )
        return 2
    try:
        result = run(args)
        write(result, _format(args), args.output)
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except SeekError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # SDK errors: auth, credits, blocked after retries, ...
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    if args.output:
        count = len(result) if isinstance(result, list) else 1
        print(f"wrote {count} record(s) to {args.output}", file=sys.stderr)
    return 0
