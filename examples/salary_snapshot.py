"""Compare one role across Jobstreet and JobsDB: job counts, remote share and pay.

    python examples/salary_snapshot.py "software engineer"

For each market it makes two requests: the facet counts (total jobs, remote and
hybrid jobs) and the 100 most relevant jobs, whose monthly salaries are summarised.
Only salaries the advertisers actually show are used.
"""

from __future__ import annotations

import statistics
import sys

from seek_scraper import SeekScraper

MARKETS = ("sg", "my", "ph", "id", "hk", "th")


def main() -> None:
    role = " ".join(sys.argv[1:]) or "software engineer"
    seek = SeekScraper()
    print(f"{'market':<8}{'jobs':>8}{'remote':>8}{'hybrid':>8}  monthly pay (median of shown)")
    for code in MARKETS:
        facets = seek.facets(role, market=code)
        arrangements = {row["label"]: row["count"] for row in facets.work_arrangements}
        jobs = seek.search_jobs(role, market=code, limit=100)
        midpoints = [
            (job.salary_min + job.salary_max) / 2
            for job in jobs
            if job.salary_period == "month" and job.salary_min and job.salary_max
        ]
        pay = "-"
        if midpoints:
            currency = jobs[0].salary_currency or ""
            pay = f"{currency} {statistics.median(midpoints):,.0f} from {len(midpoints)} ads"
        print(
            f"{code:<8}{facets.total:>8}{arrangements.get('Remote', 0):>8}"
            f"{arrangements.get('Hybrid', 0):>8}  {pay}"
        )
    print(f"API requests: {seek.requests}")


if __name__ == "__main__":
    main()
