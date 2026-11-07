from __future__ import annotations

import pytest

from seek_scraper.salary import parse_salary, pay_period

EN_DASH = chr(0x2013)
NBSP = chr(0xA0)
BAHT = chr(0x0E3F)


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("$120.00 - $140.00 phr (incl. super)", (120, 140, "hour")),
        (f"RM{NBSP}6,000 {EN_DASH} RM{NBSP}8,000 per month", (6000, 8000, "month")),
        (f"Earn $116,413 {EN_DASH} $140,849 per year + super", (116413, 140849, "year")),
        (f"$116,706 {EN_DASH} $130,478 pa plus 17% Super & Benefits", (116706, 130478, "year")),
        ("$90k - $110k + super", (90000, 110000, None)),
        ("$90 - 110k package", (90000, 110000, None)),
        ("$65-75k", (65000, 75000, None)),
        (f"$59 {EN_DASH} $85 per hour", (59, 85, "hour")),
        ("$45 - $50 p/h + super", (45, 50, "hour")),
        ("$800 per day", (800, 800, "day")),
        ("$1,234.56 per week", (1234.56, 1234.56, "week")),
        ("Rp 5.000.000 - Rp 7.000.000 per bulan", (5_000_000, 7_000_000, "month")),
        ("Rp 5 - 7 juta", (5_000_000, 7_000_000, None)),
        (f"{BAHT}30,000 - {BAHT}45,000 per month", (30000, 45000, "month")),
        ("HK$18,000 - HK$22,000 /month", (18000, 22000, "month")),
        ("Php 25,000 - 30,000 monthly", (25000, 30000, "month")),
        ("$100,000 - $120,000 + 11.5% super", (100000, 120000, None)),
        ("Base $150K + Super + Bonus", (150000, 150000, None)),
        ("$85,000 + super", (85000, 85000, None)),
    ],
)
def test_ranges_and_periods(label, expected):
    salary = parse_salary(label, "AUD")
    assert (salary.min, salary.max, salary.period) == expected
    assert salary.currency == "AUD"


@pytest.mark.parametrize(
    ("label", "low", "high"),
    [
        ("Up to $85,000", None, 85000),
        ("From $70k", 70000, None),
        ("$85k+", 85000, None),
        ("Starting at $60 per hour", 60, None),
    ],
)
def test_open_ended(label, low, high):
    salary = parse_salary(label, "AUD")
    assert (salary.min, salary.max) == (low, high)


@pytest.mark.parametrize(
    "label",
    [
        None,
        "",
        "Competitive",
        "Salary is aligned to RN Level",
        "12 + 12 + 12 months, $$$ negotiable",
        "800",  # a bare number is not money
        "Level 5, 17% super",
    ],
)
def test_no_amount(label):
    salary = parse_salary(label, "AUD")
    assert salary.min is None and salary.max is None
    assert salary.currency is None


def test_period_without_amount_is_still_reported():
    assert parse_salary("Attractive hourly rate").period == "hour"


@pytest.mark.parametrize(
    ("label", "period"),
    [
        ("$30 per hour", "hour"),
        ("$95,000 p.a.", "year"),
        ("$95,000 per annum", "year"),
        ("$95,000 annually", "year"),
        ("$1,800 per week", "week"),
        ("$7,000 a month", "month"),
        ("$95,000 package", None),
        # The earliest stated period wins.
        ("$45 per hour (about $90,000 per year)", "hour"),
    ],
)
def test_pay_period(label, period):
    assert pay_period(label) == period


def test_small_amounts_are_not_mistaken_for_times():
    assert pay_period("Shifts 9 to 5pm, $35 per hour") == "hour"
