# SEEK Scraper (SEEK, Jobstreet, JobsDB)

[![CI](https://github.com/ScrapeUnblocker/seek-scraper/actions/workflows/ci.yml/badge.svg)](https://github.com/ScrapeUnblocker/seek-scraper/actions/workflows/ci.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Powered by ScrapeUnblocker](https://img.shields.io/badge/powered%20by-ScrapeUnblocker-6f42c1.svg)](https://scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos)

**Scrape job listings from [SEEK](https://www.seek.com.au), [Jobstreet](https://my.jobstreet.com)
and [JobsDB](https://hk.jobsdb.com) into clean JSON or CSV: job search with the sites' own
filters in eight countries, full job details with the employer's company profile, job
counts by work type, work arrangement and salary, and alerts for new jobs.**

SEEK, Jobstreet and JobsDB run on one platform, so one scraper covers all of them:

| Market | Site | `--market` | Currency |
| --- | --- | --- | --- |
| Australia | SEEK | `au` (default) | AUD |
| New Zealand | SEEK | `nz` | NZD |
| Malaysia | Jobstreet | `my` | MYR |
| Singapore | Jobstreet | `sg` | SGD |
| Philippines | Jobstreet | `ph` | PHP |
| Indonesia | Jobstreet | `id` | IDR |
| Hong Kong | JobsDB | `hk` | HKD |
| Thailand | JobsDB | `th` | THB |

Powered by [ScrapeUnblocker](https://scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos):
every request goes through the `getPageSource` API with the official Python SDK. Search
reads the JSON the sites' own search pages load (up to 100 jobs per request), and job
details come from the data embedded in the job page. You don't need an account, cookies,
a headless browser or retry logic of your own.

## Features

- **Job search** in any of the eight markets, by keywords and location (`"Sydney"`,
  `"All Melbourne VIC"`, `"Parramatta"`, `"Kuala Lumpur"`, `"Bangkok"`), with the site
  filters: classification (30 categories, by id, slug or alias such as `it` or
  `healthcare`), subclassification, work type (full-time, part-time, contract, casual),
  work arrangement (on-site, hybrid, remote), salary range and salary type (annual,
  monthly, hourly), listed within 1/3/7/14/31 days, and sort by relevance or date.
- **Up to 100 jobs per request**, multi-page collection, several keywords x several
  locations in one run, deduplicated by job id.
- **Every job card**: job id, title, URL, company, advertiser id, private-advertiser flag,
  location and location hierarchy, country, classification and subclassification (names
  and ids), work types, work arrangements, salary label, teaser, bullet points, badges
  ("Be an early applicant", "Immediate start"), featured flag, listing date, logo.
- **Salary parsing**: the free-text salary label (`"$120.00 - $140.00 phr (incl. super)"`,
  `"RM 6,000 - RM 8,000 per month"`, `"Rp 5.000.000 - Rp 7.000.000 per month"`) becomes
  `salary_min`, `salary_max`, `salary_period` (hour / day / week / month / year, only when
  the label says so) and the market's currency. The original label is always kept.
- **Full job details** (`job`, or `search --details`): status (active or expired), listing
  and expiry dates, plain-text and HTML description, suburb / state / postcode / country,
  area, work type and arrangement, salary, advertiser (verified flag, registration date),
  the employer's **screening questions**, video, logo and cover image, whether "Apply"
  goes to the employer's own site, and the **company profile**: rating, review count,
  industry, size, website, overview and perks.
- **Facet counts** (`facets`): total jobs for a search and how they split by work type,
  work arrangement and salary floor, plus SEEK's related searches - in one request.
- **New-job alerts** (`watch`): run a saved search on a schedule and get only the jobs
  that are new since the last run.
- **Output** as a terminal table, JSON, JSON Lines or CSV (Excel-friendly UTF-8).
- Retries with backoff on throttling, timeouts and blocks; offline test suite.

## Install

```bash
git clone https://github.com/ScrapeUnblocker/seek-scraper.git
cd seek-scraper
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install .
```

Get an API key at [scrapeunblocker.com](https://scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos)
and put it in the environment (see `.env.example`):

```bash
export SCRAPEUNBLOCKER_KEY=your_key_here          # Windows: set SCRAPEUNBLOCKER_KEY=...
```

## CLI usage

```bash
# Data engineer jobs in Sydney listed in the last 7 days
seek-scraper search "data engineer" --where "All Sydney NSW" --listed-within 7

# Remote or hybrid IT jobs paying 150k+ a year, newest first, as CSV
seek-scraper search "python" -c it --remote --hybrid --salary-min 150000 \
    --salary-type annual --sort date -n 200 -o python_jobs.csv

# Several keywords x several cities in one run (merged, deduplicated)
seek-scraper search "nurse" "midwife" -w "All Melbourne VIC" -w "All Brisbane QLD" \
    --work-type full-time,part-time -o nursing.jsonl

# Jobstreet and JobsDB
seek-scraper search "accountant" -m my -w "Kuala Lumpur"
seek-scraper search "software engineer" -m sg --listed-within 7
seek-scraper search "marketing" -m th -w Bangkok
seek-scraper search "admin" -m id -w "Jakarta Raya" --salary-type monthly

# Every page SEEK serves for a search (about 550 jobs at most)
seek-scraper search "electrician" -m nz --all -o electricians.csv

# Search, then open every job page (one extra request per job)
seek-scraper search "data engineer" -w Melbourne -n 10 --details -o details.json

# Full details for job ids or URLs from any of the sites
seek-scraper job 95747137
seek-scraper job https://sg.jobstreet.com/job/95745590 https://hk.jobsdb.com/job/95756872

# Job counts by work type, work arrangement and salary floor
seek-scraper facets nurse -w "All Melbourne VIC"

# Job alert: only jobs that are new since the last run
seek-scraper watch "registered nurse" -w "All Melbourne VIC" --state nurse-watch.json

# Offline helpers
seek-scraper classifications
seek-scraper markets
```

Output goes to the terminal as a table by default (`job` prints JSON). Pick a format with
`-f table|json|jsonl|csv`, or write a file with `-o` (the format follows the extension).
Run `seek-scraper <command> --help` for every option.

| Option | Meaning |
| --- | --- |
| `-m, --market` | `au`, `nz`, `my`, `sg`, `ph`, `id`, `hk`, `th` |
| `-w, --where` | location as typed on the site; repeat for several |
| `-c, --classification` | id (`6281`), slug or alias (`it`, `hr`, `healthcare`, ...) |
| `--subclassification` | subclassification id (see a job's `subclassification_id`) |
| `--work-type` | `full-time`, `part-time`, `contract`, `casual` |
| `--work-arrangement`, `--remote`, `--hybrid` | `on-site`, `hybrid`, `remote` |
| `--salary-min`, `--salary-max`, `--salary-type` | salary range in `annual`, `monthly` or `hourly` terms |
| `--listed-within` | 1, 3, 7, 14 or 31 days |
| `--sort` | `relevance` (default) or `date` |
| `-n, --limit` / `--all` | jobs per search (default 100) / every page |
| `--details` | open each job page from the search results |
| `--country` | route requests through another country (default: automatic) |

## Library usage

```python
from seek_scraper import SearchFilters, SeekScraper

seek = SeekScraper()  # reads SCRAPEUNBLOCKER_KEY

# One search, as many pages as needed
jobs = seek.search_jobs(
    "data engineer",
    "All Sydney NSW",
    SearchFilters(work_arrangements=["hybrid", "remote"], listed_within_days=7),
    limit=50,
)
for job in jobs:
    print(job.title, job.company, job.salary or job.salary_label)

# One page, with the total and the location SEEK matched
page = seek.search("nurse", "Parramatta", market="au", page=1, page_size=100)
print(page.total, page.location, page.has_next)

# Several keywords x locations, deduplicated
jobs = seek.collect(["accountant", "auditor"], ["Kuala Lumpur", "Selangor"], market="my")

# Full details: by id (with market) or by URL
details = seek.job("95745590", market="sg")
print(details.questions, details.company_profile.rating)

# Facet counts for one search
facets = seek.facets("nurse", "All Melbourne VIC")
print(facets.total, facets.work_arrangements, facets.salary_at_least)

# New jobs since the last run
new = seek.watch("seek-watch.json", ["registered nurse"], ["All Melbourne VIC"])

# Salary parsing on its own
from seek_scraper import parse_salary

parse_salary("RM 6,000 - RM 8,000 per month", "MYR")
# Salary(min=6000, max=8000, period='month', currency='MYR')
```

Write results with `seek_scraper.write(records, "csv", "jobs.csv")` or
`seek_scraper.to_csv_file(records, path)`. Every record also has `.to_dict()`.

Runnable scripts in [`examples/`](examples):

- [`remote_jobs_to_csv.py`](examples/remote_jobs_to_csv.py) - remote and hybrid tech jobs
  from SEEK Australia and New Zealand into one CSV.
- [`salary_snapshot.py`](examples/salary_snapshot.py) - one role across the six
  Jobstreet and JobsDB markets: job counts, remote share and median advertised pay.
- [`new_jobs_alert.py`](examples/new_jobs_alert.py) - a job alert for cron or Task
  Scheduler.

## Example output

`seek-scraper search "software engineer" -m sg --listed-within 7 -n 6`:

```text
job_id    listed      title              company                            location                     work type                          salary
95750518  2026-11-06  Software Engineer  OCBC Bank                          Singapore                    Full time, On-site
95745590  2026-11-06  Software Engineer  Certis Group                       Central Region               Full time, Hybrid                  SGD 5,500-7,700/mo
95755147  2026-11-06  Software Engineer  Savant Infotech Solutions Pte Ltd  Singapore                    Contract/Temp, Full time, On-site
95751232  2026-11-06  Software Engineer  novaCITYNETS Pte Ltd               Macpherson, Central Region   Full time, On-site
95708834  2026-11-05  Software Engineer  Aztech Technologies Pte Ltd        Kampong Ubi, Central Region  Full time, On-site                 SGD 4,800-6,500/mo
95723229  2026-11-05  Software Engineer  G and B Service                    Singapore                    Contract/Temp, Full time, On-site
```

`seek-scraper job https://sg.jobstreet.com/job/95745590` (long text shortened):

```json
{
  "job_id": "95745590",
  "title": "Software Engineer",
  "url": "https://sg.jobstreet.com/job/95745590",
  "market": "sg",
  "status": "Active",
  "is_expired": false,
  "listed_at": "2026-11-06T07:36:20.150Z",
  "expires_at": "2026-12-06T12:59:59.999Z",
  "company": "Certis Group",
  "advertiser_name": "CERTIS GROUP - GHR",
  "advertiser_verified": true,
  "location": "Central Region",
  "country": "Singapore",
  "classification": "Information & Communication Technology",
  "subclassification": "Developers/Programmers",
  "work_type": "Full time",
  "work_arrangements": ["Hybrid"],
  "salary_label": "$5,500 – $7,700 per month",
  "salary_min": 5500,
  "salary_max": 7700,
  "salary_period": "month",
  "salary_currency": "SGD",
  "description_text": "Role Summary\n\nThe Platform Software Developer is responsible for ...",
  "questions": [
    "Which of the following statements best describes your right to work in Singapore?",
    "What's your expected monthly basic salary?",
    "How many years' experience do you have as a Software Developer?",
    "Do you have experience using C#.NET Programming Language?"
  ],
  "applies_on_employer_site": false,
  "company_jobs_url": "https://sg.jobstreet.com/Certis-Group-jobs/at-this-company",
  "company_profile": {
    "name": "Certis Group",
    "url": "https://sg.jobstreet.com/companies/certis-group-168556355285529",
    "industry": "Corrective & Security Services",
    "size": "More than 10,000 employees",
    "website": "https://www.certisgroup.com/",
    "rating": 3.8,
    "reviews_count": 213,
    "perks": ["Medical", "Miscellaneous allowance", "Education support", "Dental"]
  }
}
```

`seek-scraper facets nurse -w "All Melbourne VIC"`:

```text
facet             value             jobs
total             all jobs          1292
work_type         Full Time         558
work_type         Part Time         407
work_type         Casual/Vacation   186
work_type         Contract/Temp     158
work_arrangement  On-site           1160
work_arrangement  Hybrid            106
work_arrangement  Remote            26
salary_at_least   AUD 80,000        1121
salary_at_least   AUD 100,000       886
salary_at_least   AUD 120,000       576
salary_at_least   AUD 150,000       255
related_search    registered nurse  1805
related_search    enrolled nurse    933
related_search    practice nurse    762
```

## How it works

- **Search** calls `/api/jobsearch/v5/search` on the market's own host with the same
  parameters the site's search page sends (`keywords`, `where`, `classification`,
  `worktype`, `workarrangement`, `salaryrange`, `salarytype`, `daterange`, `sortmode`,
  `page`, `pageSize`). The JSON can come back as-is or wrapped in the browser's plain-text
  view; both are handled.
- **Job details** read `window.SEEK_REDUX_DATA` from the server-rendered `/job/<id>` page.
  Job pages are routed through the market's own country by default.
- Each page is one plain `getPageSource` call (no browser rendering). Throttled,
  blocked and timed-out requests are retried with doubling backoff, a response without
  the expected data is fetched once more, and an unknown job id raises
  `JobNotFoundError`.

Things worth knowing:

- SEEK serves roughly the first **550 jobs** of any search. To collect more, split the
  search by location, classification, work type or salary band; `collect()` merges and
  deduplicates the results.
- The salary filter also matches jobs whose salary is hidden from the ad (advertisers
  give SEEK a range even when they don't show it), so filtered results can include jobs
  with no salary label. Facet counts work the same way.
- `where` is free text. SEEK resolves it and `SearchPage.location` shows what it matched;
  an unknown place returns no jobs and logs a warning.
- Expired jobs still open with `status: "Expired"` for a while.
- The scraper does not collect the names, photos or phone numbers of individual
  recruiters that some ads show.

## Project layout

```text
seek-scraper/
├── src/seek_scraper/
│   ├── __init__.py      # public API
│   ├── scraper.py       # SeekScraper: fetch, retry, search, collect, job, facets, watch
│   ├── parsing.py       # search JSON and job pages -> records
│   ├── urls.py          # SearchFilters, search API and job URLs, job id parsing
│   ├── markets.py       # the eight sites, classifications, work types, arrangements
│   ├── salary.py        # salary label -> min / max / period / currency
│   ├── models.py        # dataclasses with JSON / CSV / table layouts
│   ├── monitor.py       # watch-mode state
│   ├── export.py        # JSON, JSON Lines, CSV, table
│   └── cli.py           # seek-scraper command
├── examples/            # runnable scripts
├── tests/               # offline tests (fake SDK client, no API calls)
├── pyproject.toml
├── requirements.txt
├── Makefile
└── .github/workflows/ci.yml
```

## Development

```bash
python -m venv .venv && source .venv/bin/activate
make install   # pip install -e ".[dev]"
make lint      # ruff check + ruff format --check
make test      # pytest, offline
```

The tests build small responses in the shape of real SEEK ones and replace the SDK client
with a fake one, so they run without an API key and spend no credit.

## Links

- [ScrapeUnblocker](https://scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos)
- [ScrapeUnblocker documentation](https://docs.scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos)
- [Python SDK on PyPI](https://pypi.org/project/scrapeunblocker/)

Use the data responsibly and in line with the sites' terms and the law that applies to
you; job ads belong to the employers who published them.

## License

[MIT](LICENSE)
