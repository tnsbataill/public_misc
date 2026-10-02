"""Definitions shared by the XML and COM backends."""

from __future__ import annotations

from datetime import date, datetime


class ProjectError(Exception):
    """A user-facing error (bad UID, no open project, ...)."""


LINK_TYPES = {"FF": 0, "FS": 1, "SF": 2, "SS": 3}
LINK_NAMES = {v: k for k, v in LINK_TYPES.items()}

CONSTRAINT_NAMES = {
    0: "ASAP",  # As Soon As Possible
    1: "ALAP",  # As Late As Possible
    2: "MSO",  # Must Start On
    3: "MFO",  # Must Finish On
    4: "SNET",  # Start No Earlier Than
    5: "SNLT",  # Start No Later Than
    6: "FNET",  # Finish No Earlier Than
    7: "FNLT",  # Finish No Later Than
}
CONSTRAINT_TYPES = {v: k for k, v in CONSTRAINT_NAMES.items()}

RESOURCE_TYPES = {"material": 0, "work": 1, "cost": 2}
RESOURCE_TYPE_NAMES = {v: k for k, v in RESOURCE_TYPES.items()}


def link_type_code(name: str) -> int:
    try:
        return LINK_TYPES[name.upper()]
    except KeyError:
        raise ProjectError(f"Unknown link type {name!r}; use one of {sorted(LINK_TYPES)}") from None


def constraint_code(name: str) -> int:
    try:
        return CONSTRAINT_TYPES[name.upper()]
    except KeyError:
        raise ProjectError(f"Unknown constraint {name!r}; use one of {sorted(CONSTRAINT_TYPES)}") from None


def resource_type_code(name: str) -> int:
    try:
        return RESOURCE_TYPES[name.lower()]
    except KeyError:
        raise ProjectError(f"Unknown resource type {name!r}; use one of {sorted(RESOURCE_TYPES)}") from None


def parse_when(value: str | date | datetime, default_hour: int = 8) -> datetime:
    """Accept 'YYYY-MM-DD' or an ISO datetime; a bare date means 08:00 that day."""
    if isinstance(value, datetime):
        return value.replace(tzinfo=None, microsecond=0)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, default_hour)
    text = value.strip()
    try:
        if len(text) == 10:
            d = date.fromisoformat(text)
            return datetime(d.year, d.month, d.day, default_hour)
        return datetime.fromisoformat(text).replace(tzinfo=None, microsecond=0)
    except ValueError:
        raise ProjectError(f"Invalid date {value!r}; use YYYY-MM-DD or YYYY-MM-DDTHH:MM") from None


def iso(dt: datetime | None) -> str | None:
    return dt.isoformat(timespec="minutes") if dt else None


def round_days(minutes: float, minutes_per_day: float) -> float:
    return round(minutes / minutes_per_day, 3)
