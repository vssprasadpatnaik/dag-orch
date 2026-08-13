"""Time helpers for the rules predictor (naive ISO times keep the POC simple)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from config import BUSINESS_DATE

FMT = "%Y-%m-%dT%H:%M:%S"


def parse(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    return datetime.strptime(ts, FMT)


def fmt(dt: Optional[datetime]) -> Optional[str]:
    return None if dt is None else dt.strftime(FMT)


def hhmm(ts: Optional[str]) -> str:
    dt = parse(ts)
    return "" if dt is None else dt.strftime("%H:%M")


def deadline_for(local_hhmm: str) -> str:
    """'08:00' -> '<business_date>T08:00:00'."""
    return "{0}T{1}:00".format(BUSINESS_DATE, local_hhmm)


def add_minutes(ts: str, minutes: float) -> str:
    return fmt(parse(ts) + timedelta(minutes=minutes))


def minutes_between(a: str, b: str) -> float:
    """b - a in minutes (negative if b is earlier)."""
    return (parse(b) - parse(a)).total_seconds() / 60.0
