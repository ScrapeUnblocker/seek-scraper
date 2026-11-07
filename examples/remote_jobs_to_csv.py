"""Collect remote and hybrid tech jobs from SEEK Australia and New Zealand into one CSV.

    python examples/remote_jobs_to_csv.py "data engineer" "analytics engineer"

Each keyword is searched on both sites (last 14 days, up to 100 jobs per search);
jobs are deduplicated by id and written to ``remote_jobs.csv``.
"""

from __future__ import annotations

import sys

from seek_scraper import SearchFilters, SeekScraper, to_csv_file


def main() -> None:
    keywords = sys.argv[1:] or ["data engineer"]
    seek = SeekScraper()
    filters = SearchFilters(
        classifications=["it"],
        work_arrangements=["remote", "hybrid"],
        listed_within_days=14,
    )
    jobs = []
    for market in ("au", "nz"):
        found = seek.collect(keywords, filters=filters, market=market, limit_per_search=100)
        print(f"{market}: {len(found)} jobs", file=sys.stderr)
        jobs.extend(found)

    to_csv_file(jobs, "remote_jobs.csv")
    with_salary = sum(1 for job in jobs if job.salary_min or job.salary_max)
    print(f"wrote {len(jobs)} jobs ({with_salary} with a salary) to remote_jobs.csv")
    print(f"API requests: {seek.requests}")


if __name__ == "__main__":
    main()
