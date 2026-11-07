"""A job alert: print jobs that are new since the last run.

    python examples/new_jobs_alert.py

Run it from cron or Task Scheduler. The first run saves the current jobs as the
baseline; later runs print only jobs SEEK has listed since. Edit the search below.
"""

from __future__ import annotations

from seek_scraper import SearchFilters, SeekScraper

STATE_FILE = "seek-watch-nurse-melbourne.json"


def main() -> None:
    seek = SeekScraper()
    new = seek.watch(
        STATE_FILE,
        keywords=["registered nurse"],
        wheres=["All Melbourne VIC"],
        filters=SearchFilters(work_types=["full-time", "part-time"], sort="date"),
        limit_per_search=100,
    )
    if not new:
        print("no new jobs")
        return
    for job in new:
        pay = job.salary or job.salary_label or "salary not shown"
        print(f"{job.title} - {job.company} - {job.location} - {pay}")
        print(f"  {job.url}")


if __name__ == "__main__":
    main()
