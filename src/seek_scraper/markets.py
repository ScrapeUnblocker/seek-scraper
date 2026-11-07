"""SEEK's job sites and the codes its search API uses.

SEEK runs one platform for eight markets: SEEK in Australia and New Zealand, Jobstreet
in Malaysia, Singapore, the Philippines and Indonesia, and JobsDB in Hong Kong and
Thailand. Every site answers the same search API and serves the same job pages, so one
scraper covers all of them. Classification, work type and work arrangement ids are
shared across the sites; only the labels are localised.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .errors import InputError


@dataclass(frozen=True)
class Market:
    """One SEEK job site."""

    code: str
    name: str
    host: str
    site_key: str
    locale: str
    currency: str
    country: str

    @property
    def base_url(self) -> str:
        return f"https://{self.host}"

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "name": self.name,
            "url": self.base_url,
            "site_key": self.site_key,
            "locale": self.locale,
            "currency": self.currency,
        }

    TABLE_HEADER = ("code", "site", "url", "currency")

    def table_row(self) -> tuple[str, ...]:
        return (self.code, self.name, self.base_url, self.currency)


MARKETS: dict[str, Market] = {
    m.code: m
    for m in (
        Market("au", "SEEK Australia", "www.seek.com.au", "AU-Main", "en-AU", "AUD", "au"),
        Market("nz", "SEEK New Zealand", "www.seek.co.nz", "NZ-Main", "en-NZ", "NZD", "nz"),
        Market("my", "Jobstreet Malaysia", "my.jobstreet.com", "MY-Main", "en-MY", "MYR", "my"),
        Market("sg", "Jobstreet Singapore", "sg.jobstreet.com", "SG-Main", "en-SG", "SGD", "sg"),
        Market("ph", "Jobstreet Philippines", "ph.jobstreet.com", "PH-Main", "en-PH", "PHP", "ph"),
        Market("id", "Jobstreet Indonesia", "id.jobstreet.com", "ID-Main", "en-ID", "IDR", "id"),
        Market("hk", "JobsDB Hong Kong", "hk.jobsdb.com", "HK-Main", "en-HK", "HKD", "hk"),
        Market("th", "JobsDB Thailand", "th.jobsdb.com", "TH-Main", "en-TH", "THB", "th"),
    )
}

#: Hosts that serve a market under another name (SEEK's share links use au.seek.com).
_HOST_ALIASES = {"au.seek.com": "au", "seek.com.au": "au", "nz.seek.com": "nz", "seek.co.nz": "nz"}


def get_market(code: str | Market) -> Market:
    """The market for a code such as ``"au"`` or ``"sg"`` (case-insensitive)."""
    if isinstance(code, Market):
        return code
    key = (code or "").strip().lower()
    if key in MARKETS:
        return MARKETS[key]
    raise InputError(f"unknown market {code!r}; choose from: {', '.join(MARKETS)}")


def market_for_host(host: str) -> Market | None:
    """The market a SEEK, Jobstreet or JobsDB hostname belongs to, if any."""
    host = _bare_host(host)
    if host in _HOST_ALIASES:
        return MARKETS[_HOST_ALIASES[host]]
    for market in MARKETS.values():
        if host == _bare_host(market.host):
            return market
    return None


def _bare_host(host: str) -> str:
    host = (host or "").strip().lower().split(":")[0]
    return host[4:] if host.startswith("www.") else host


# -- search vocabulary ---------------------------------------------------------------


@dataclass(frozen=True)
class Classification:
    """A top-level SEEK job classification (the "All classifications" menu)."""

    id: str
    name: str
    slug: str

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "slug": self.slug, "name": self.name}

    TABLE_HEADER = ("id", "slug", "classification")

    def table_row(self) -> tuple[str, ...]:
        return (self.id, self.slug, self.name)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower().replace("&", " ")).strip("-")


#: The 30 classifications in SEEK's search menu (ids are shared by every market).
CLASSIFICATIONS: tuple[Classification, ...] = tuple(
    Classification(cid, name, _slug(name))
    for cid, name in (
        ("1200", "Accounting"),
        ("6251", "Administration & Office Support"),
        ("6304", "Advertising, Arts & Media"),
        ("1203", "Banking & Financial Services"),
        ("1204", "Call Centre & Customer Service"),
        ("7019", "CEO & General Management"),
        ("6163", "Community Services & Development"),
        ("1206", "Construction"),
        ("6076", "Consulting & Strategy"),
        ("6263", "Design & Architecture"),
        ("6123", "Education & Training"),
        ("1209", "Engineering"),
        ("6205", "Farming, Animals & Conservation"),
        ("1210", "Government & Defence"),
        ("1211", "Healthcare & Medical"),
        ("1212", "Hospitality & Tourism"),
        ("6317", "Human Resources & Recruitment"),
        ("6281", "Information & Communication Technology"),
        ("1214", "Insurance & Superannuation"),
        ("1216", "Legal"),
        ("6092", "Manufacturing, Transport & Logistics"),
        ("6008", "Marketing & Communications"),
        ("6058", "Mining, Resources & Energy"),
        ("1220", "Real Estate & Property"),
        ("6043", "Retail & Consumer Products"),
        ("6362", "Sales"),
        ("1223", "Science & Technology"),
        ("6261", "Self Employment"),
        ("6246", "Sport & Recreation"),
        ("1225", "Trades & Services"),
    )
)

#: Short names people actually type.
_CLASSIFICATION_ALIASES = {
    "it": "6281",
    "ict": "6281",
    "tech": "6281",
    "admin": "6251",
    "banking": "1203",
    "finance": "1203",
    "customer-service": "1204",
    "management": "7019",
    "consulting": "6076",
    "design": "6263",
    "education": "6123",
    "farming": "6205",
    "government": "1210",
    "healthcare": "1211",
    "hospitality": "1212",
    "hr": "6317",
    "insurance": "1214",
    "manufacturing": "6092",
    "logistics": "6092",
    "marketing": "6008",
    "mining": "6058",
    "real-estate": "1220",
    "retail": "6043",
    "science": "1223",
    "sport": "6246",
    "trades": "1225",
}


def classification_id(value: str) -> str:
    """A classification id from an id, a slug (``information-communication-technology``),
    the full name or a short alias (``it``, ``hr``, ``healthcare``)."""
    text = (value or "").strip()
    if text.isdigit():
        return text
    key = _slug(text)
    if key in _CLASSIFICATION_ALIASES:
        return _CLASSIFICATION_ALIASES[key]
    for item in CLASSIFICATIONS:
        if key == item.slug:
            return item.id
    matches = [item for item in CLASSIFICATIONS if item.slug.startswith(key)] if key else []
    if len(matches) == 1:
        return matches[0].id
    raise InputError(
        f"unknown classification {value!r}; run `seek-scraper classifications` for the list"
    )


#: Work types (``worktype``) - ids from SEEK's own search facets.
WORK_TYPES = {
    "full-time": "242",
    "part-time": "243",
    "contract": "244",
    "casual": "245",
}
_WORK_TYPE_ALIASES = {"fulltime": "242", "parttime": "243", "temp": "244", "contract-temp": "244"}

#: Work arrangements (``workarrangement``).
WORK_ARRANGEMENTS = {"on-site": "1", "hybrid": "2", "remote": "3"}
_ARRANGEMENT_ALIASES = {"onsite": "1", "office": "1", "wfh": "3", "work-from-home": "3"}

#: Listing-date windows (``daterange``) offered by SEEK's "Listed any time" menu.
LISTED_WITHIN_DAYS = (1, 3, 7, 14, 31)

#: Salary types (``salarytype``).
SALARY_TYPES = ("annual", "monthly", "hourly")

#: Sort orders (``sortmode``).
SORTS = {"relevance": "KeywordRelevance", "date": "ListedDate"}


def _lookup(value: str, table: dict[str, str], aliases: dict[str, str], what: str) -> str:
    key = _slug(value)
    if key in table:
        return table[key]
    if key in aliases:
        return aliases[key]
    if value.strip() in table.values():
        return value.strip()
    raise InputError(f"unknown {what} {value!r}; choose from: {', '.join(table)}")


def work_type_id(value: str) -> str:
    return _lookup(value, WORK_TYPES, _WORK_TYPE_ALIASES, "work type")


def work_arrangement_id(value: str) -> str:
    return _lookup(value, WORK_ARRANGEMENTS, _ARRANGEMENT_ALIASES, "work arrangement")
