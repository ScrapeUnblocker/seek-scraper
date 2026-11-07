"""Remember which jobs a saved search has already shown (for :meth:`SeekScraper.watch`)."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from datetime import datetime, timezone

from .models import Job

#: How many job ids a state file keeps (the most recently seen).
MAX_REMEMBERED = 5000


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_seen(path: str) -> dict[str, str] | None:
    """``{job_id: first_seen}`` from the state file, or ``None`` on the first run."""
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    seen = data.get("seen") if isinstance(data, dict) else None
    return {str(k): str(v) for k, v in seen.items()} if isinstance(seen, dict) else {}


def save_seen(path: str, seen: dict[str, str], *, keep: int = MAX_REMEMBERED) -> None:
    """Write the state file, keeping the ``keep`` most recently seen ids."""
    items = sorted(seen.items(), key=lambda kv: kv[1], reverse=True)[:keep]
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump({"seen": dict(sorted(items))}, handle, indent=1)
        handle.write("\n")


def new_jobs(
    jobs: Iterable[Job], seen: dict[str, str] | None, when: str | None = None
) -> tuple[list[Job], dict[str, str]]:
    """Jobs not in ``seen`` and the updated ``seen`` map (``seen`` itself is not changed)."""
    stamp = when or now_iso()
    updated = dict(seen or {})
    fresh = []
    for job in jobs:
        if job.job_id in updated:
            continue
        updated[job.job_id] = stamp
        fresh.append(job)
    return fresh, updated
