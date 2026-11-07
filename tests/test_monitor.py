from __future__ import annotations

from conftest import card

from seek_scraper import get_market
from seek_scraper.monitor import load_seen, new_jobs, save_seen
from seek_scraper.parsing import parse_card

AU = get_market("au")


def jobs(*ids: str):
    return [parse_card(card(i), AU) for i in ids]


def test_first_run_everything_is_new():
    fresh, seen = new_jobs(jobs("1", "2"), None, "2026-11-07T00:00:00Z")
    assert [j.job_id for j in fresh] == ["1", "2"]
    assert seen == {"1": "2026-11-07T00:00:00Z", "2": "2026-11-07T00:00:00Z"}


def test_known_jobs_are_skipped_and_dates_kept():
    before = {"1": "2026-11-01T00:00:00Z"}
    fresh, seen = new_jobs(jobs("1", "3", "3"), before, "2026-11-07T00:00:00Z")
    assert [j.job_id for j in fresh] == ["3"]
    assert seen["1"] == "2026-11-01T00:00:00Z"
    assert before == {"1": "2026-11-01T00:00:00Z"}  # not changed in place


def test_state_round_trip(tmp_path):
    path = tmp_path / "sub" / "state.json"
    assert load_seen(str(path)) is None
    save_seen(str(path), {"2": "2026-11-02T00:00:00Z", "1": "2026-11-01T00:00:00Z"})
    assert load_seen(str(path)) == {"1": "2026-11-01T00:00:00Z", "2": "2026-11-02T00:00:00Z"}


def test_state_keeps_the_most_recent(tmp_path):
    path = tmp_path / "state.json"
    seen = {str(i): f"2026-11-{i:02d}T00:00:00Z" for i in range(1, 11)}
    save_seen(str(path), seen, keep=3)
    assert sorted(load_seen(str(path))) == ["10", "8", "9"]
