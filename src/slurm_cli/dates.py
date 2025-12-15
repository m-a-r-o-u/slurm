"""Date normalization helpers for SLURM CLI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from calendar import monthrange


class DateRangeError(ValueError):
    """Raised when date ranges cannot be resolved."""


@dataclass(frozen=True)
class DateRange:
    """Inclusive date range with resolved boundaries."""

    start: date
    end: date

    def days(self) -> int:
        """Number of days in the range, inclusive."""
        delta = self.end - self.start
        return delta.days + 1


def _parse_start(value: str) -> date:
    """Parse a flexible start date value to a concrete date.

    Supported formats: YYYY, YYYY-MM, YYYY-MM-DD.
    """

    try:
        if len(value) == 4:
            return date(int(value), 1, 1)
        if len(value) == 7:
            return date.fromisoformat(f"{value}-01")
        return date.fromisoformat(value)
    except ValueError as exc:  # noqa: B904
        raise DateRangeError(f"Invalid start date '{value}'. Use YYYY, YYYY-MM, or YYYY-MM-DD.") from exc


def _last_day_of_month(year: int, month: int) -> date:
    day = monthrange(year, month)[1]
    return date(year, month, day)


def _derive_end(start: date, explicit_end: str | None) -> date:
    if explicit_end:
        try:
            parsed_end = datetime.fromisoformat(explicit_end).date()
        except ValueError as exc:  # noqa: B904
            raise DateRangeError(
                f"Invalid end date '{explicit_end}'. Use YYYY-MM-DD format."
            ) from exc
        if parsed_end < start:
            raise DateRangeError("End date cannot be before start date.")
        return parsed_end

    # derive from start precision
    if start.day != 1:
        # Provided as YYYY-MM-DD
        return _last_day_of_month(start.year, start.month)
    if start.month != 1:
        # Provided as YYYY-MM
        return _last_day_of_month(start.year, start.month)
    # Provided as YYYY
    return date(start.year, 12, 31)


def resolve_date_range(start_value: str, end_value: str | None) -> DateRange:
    """Resolve the inclusive date range based on flexible start and optional end."""

    start_date = _parse_start(start_value)
    end_date = _derive_end(start_date, end_value)
    return DateRange(start=start_date, end=end_date)
