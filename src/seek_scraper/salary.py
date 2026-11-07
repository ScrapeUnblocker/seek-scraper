"""Turn SEEK's free-text salary labels into numbers.

Advertisers write salaries any way they like: ``"$120.00 - $140.00 phr (incl. super)"``,
``"RM 6,000 - RM 8,000 per month"``, ``"Earn $116,413 - $140,849 per year + super"``,
``"$90k - $110k + super"`` or ``"Salary is aligned to RN Level"``. :func:`parse_salary`
pulls out the range and the pay period when the label states them and leaves the rest
as ``None``. It never guesses a period the label does not give; the original label is
always kept next to the parsed values.

Only figures written as money count: a currency sign (``$``, ``RM``, ``Rp``, the baht
sign, ``HK$`` ...) or a ``k`` suffix, or the other end of a range that has one. Percentages
(``+ 11.5% super``) and other numbers are ignored.
"""

from __future__ import annotations

import re
from typing import NamedTuple

_ODD_SPACES = re.compile("[\u00a0\u2007\u2009\u202f]")
_DASHES = re.compile("[\u2010-\u2015\u2212]")

_CURRENCY = (
    r"AU\$|A\$|NZ\$|SG\$|S\$|HK\$|US\$|AUD|NZD|SGD|HKD|USD|MYR|RM|IDR|Rp\.?|PHP|Php|"
    "\u20b1|THB|\u0e3f|\\$"
)
_AMOUNT = re.compile(
    r"(?P<cur>" + _CURRENCY + r")?\s?"
    r"(?P<num>\d{1,3}(?P<sep>[,.])\d{3}(?:(?P=sep)\d{3})*(?:[.,]\d{1,2})?(?!\d)"
    r"|\d+(?:[.,]\d{1,2})?(?!\d))"
    r"(?:\s?(?P<mult>[kK]|juta|jt|rb|ribu)\b)?"
    r"(?P<pct>\s?%)?"
)
_MULTIPLIERS = {"k": 1_000, "rb": 1_000, "ribu": 1_000, "jt": 1_000_000, "juta": 1_000_000}
_RANGE_JOIN = re.compile(r"^\s*(?:-|to|and|until|hingga|sampai|s/d|~)\s*$", re.IGNORECASE)
_UP_TO = re.compile(r"(?:up\s*to|max(?:imum)?|hingga|sampai|until)\W*$", re.IGNORECASE)
_FROM = re.compile(r"(?:from|starting(?:\s+at)?|min(?:imum)?|at\s+least|mulai|dari)\W*$", re.I)

#: Pay period keywords, checked case-insensitively; the earliest match in a label wins.
_PERIODS = (
    ("hour", r"per\s*h(?:ou)?r|\bp/?hr?\b|hourly|an\s+hour|/\s*h(?:ou)?r\b|per\s+jam|/\s*jam"),
    ("day", r"per\s*day|\bp/?d\b|daily|a\s+day|/\s*day\b|per\s+hari|/\s*hari"),
    ("week", r"per\s*week|\bp/?w\b|weekly|a\s+week|/\s*w(?:ee)?k\b|per\s+minggu"),
    (
        "month",
        r"per\s*month|\bp/?m\b|monthly|a\s+month|/\s*m(?:on)?th\b|/\s*mo\b|per\s+bulan"
        r"|/\s*bulan|sebulan|\u0e15\u0e48\u0e2d\u0e40\u0e14\u0e37\u0e2d\u0e19",
    ),
    ("year", r"per\s*(?:year|annum)|\bp\.?\s?a\b\.?|annual(?:ly)?|a\s+year|/\s*y(?:ea)?r\b"),
)
_PERIOD_RES = [(name, re.compile(rx, re.IGNORECASE)) for name, rx in _PERIODS]

#: Pay periods :func:`parse_salary` can report.
PERIODS = tuple(name for name, _ in _PERIODS)


class Salary(NamedTuple):
    """The numbers in a salary label. Any field can be ``None``."""

    min: float | int | None
    max: float | int | None
    period: str | None
    currency: str | None


EMPTY = Salary(None, None, None, None)


def normalise(label: str | None) -> str:
    """A label with odd spaces and dashes made plain, trimmed."""
    text = _ODD_SPACES.sub(" ", label or "")
    text = _DASHES.sub("-", text)
    return " ".join(text.split())


def pay_period(label: str | None) -> str | None:
    """``hour``, ``day``, ``week``, ``month`` or ``year`` if the label says so."""
    text = normalise(label)
    best: tuple[int, str] | None = None
    for name, rx in _PERIOD_RES:
        m = rx.search(text)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), name)
    return best[1] if best else None


def _number(match: re.Match[str]) -> float:
    raw = match.group("num")
    sep = match.group("sep")
    if sep:
        raw = raw.replace(sep, "")
    raw = raw.replace(",", ".")
    return float(raw)


def _tidy(value: float) -> float | int:
    return int(value) if float(value).is_integer() else round(value, 2)


def parse_salary(label: str | None, currency: str | None = None) -> Salary:
    """Parse a salary label.

    Args:
        label: The salary text shown on the job ad.
        currency: The currency to report when an amount is found (the market's own,
            e.g. ``AUD`` on SEEK Australia). Labels rarely name one.

    Returns:
        A :class:`Salary`. A single figure is both ``min`` and ``max``, except after
        "up to" (``max`` only) or "from" / a trailing ``+`` (``min`` only).
    """
    text = normalise(label)
    if not text:
        return EMPTY
    found = []
    for m in _AMOUNT.finditer(text):
        if m.group("pct"):
            continue
        found.append(m)
    if not found:
        return Salary(None, None, pay_period(text), None)

    def money(m: re.Match[str]) -> bool:
        return bool(m.group("cur") or m.group("mult"))

    def joined(a: re.Match[str], b: re.Match[str]) -> bool:
        return bool(_RANGE_JOIN.match(text[a.end() : b.start()]))

    low = high = None
    for i, m in enumerate(found):
        nxt = found[i + 1] if i + 1 < len(found) else None
        pair = nxt is not None and joined(m, nxt) and (money(m) or money(nxt))
        if pair:
            low, high = m, nxt
            break
        if money(m):
            low = m
            break
    if low is None:
        return Salary(None, None, pay_period(text), None)

    lo = _number(low)
    hi = _number(high) if high is not None else None
    lo_mult = (low.group("mult") or "").lower()
    hi_mult = (high.group("mult") or "").lower() if high is not None else ""
    # "$90 - 110k": the suffix on one end applies to a bare small number on the other.
    if hi is not None and hi_mult and not lo_mult and lo < 1000:
        lo_mult = hi_mult
    if hi is not None and lo_mult and not hi_mult and hi < 1000:
        hi_mult = lo_mult
    lo *= _MULTIPLIERS.get(lo_mult, 1)
    if hi is not None:
        hi *= _MULTIPLIERS.get(hi_mult, 1)
        if hi < lo:
            lo, hi = hi, lo

    if hi is None:
        before = text[: low.start()]
        # "$85k+" is a floor; "$85,000 + super" is a base salary plus extras.
        floor = text[low.end() :].startswith("+")
        if _UP_TO.search(before):
            lo, hi = None, lo
        elif floor or _FROM.search(before):
            hi = None
        else:
            hi = lo

    return Salary(
        _tidy(lo) if lo is not None else None,
        _tidy(hi) if hi is not None else None,
        pay_period(text),
        currency,
    )
