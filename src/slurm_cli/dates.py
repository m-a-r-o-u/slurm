"""Date normalization helpers for SLURM CLI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from calendar import monthrange
import re
from typing import Literal


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


def _parse_start(value: str) -> tuple[date, Literal["year", "month", "day"]]:
    """Parse a flexible start date value to a concrete date and precision.

    Supported formats: YYYY, YYYY-MM, YYYY-MM-DD.
    """

    try:
        if len(value) == 4:
            return date(int(value), 1, 1), "year"
        if len(value) == 7:
            return date.fromisoformat(f"{value}-01"), "month"
        return date.fromisoformat(value), "day"
    except ValueError as exc:  # noqa: B904
        raise DateRangeError(f"Invalid start date '{value}'. Use YYYY, YYYY-MM, or YYYY-MM-DD.") from exc


def _subtract_months(year: int, month: int, months: int) -> tuple[int, int]:
    total_months = year * 12 + (month - 1) - months
    new_year = total_months // 12
    new_month = total_months % 12 + 1
    return new_year, new_month


def _parse_relative_range(value: str, available_end: date) -> DateRange | None:
    match = re.match(r"^last([MD]):(\d+)$", value, re.IGNORECASE)
    if not match:
        return None

    unit, count_value = match.groups()
    count = int(count_value)
    if count <= 0:
        raise DateRangeError(f"Relative date '{value}' must use a positive count.")

    if unit.upper() == "D":
        start = available_end - timedelta(days=count - 1)
        return DateRange(start=start, end=available_end)

    start_year, start_month = _subtract_months(available_end.year, available_end.month, count - 1)
    start = date(start_year, start_month, 1)
    return DateRange(start=start, end=available_end)


def _last_day_of_month(year: int, month: int) -> date:
    day = monthrange(year, month)[1]
    return date(year, month, day)


def _derive_end(
    start: date,
    precision: Literal["year", "month", "day"],
    explicit_end: str | None,
    available_end: date,
) -> date:
    if explicit_end:
        try:
            parsed_end = datetime.fromisoformat(explicit_end).date()
        except ValueError as exc:  # noqa: B904
            raise DateRangeError(
                f"Invalid end date '{explicit_end}'. Use YYYY-MM-DD format."
            ) from exc
        if parsed_end < start:
            raise DateRangeError("End date cannot be before start date.")
        capped_end = min(parsed_end, available_end)
        if capped_end < start:
            raise DateRangeError(
                f"No data available for {start.isoformat()}; latest available date is {available_end.isoformat()}."
            )
        return capped_end

    # derive from start precision
    if start > available_end:
        raise DateRangeError(
            f"No data available for {start.isoformat()}; latest available date is {available_end.isoformat()}."
        )

    if precision == "day":
        derived_end = start
    elif precision == "month":
        derived_end = _last_day_of_month(start.year, start.month)
    else:
        derived_end = date(start.year, 12, 31)

    return min(derived_end, available_end)


def resolve_date_range(
    start_value: str,
    end_value: str | None,
    *,
    reference_date: date | None = None,
    use_start_precision_for_implicit_end: bool = True,
) -> DateRange:
    """Resolve the inclusive date range based on flexible start and optional end.

    The derived end date is capped at the last available day (yesterday) so that
    requests respect currently available data.
    """

    available_end = (reference_date or date.today()) - timedelta(days=1)
    if end_value is None:
        relative_range = _parse_relative_range(start_value, available_end)
        if relative_range is not None:
            return relative_range

    start_date, precision = _parse_start(start_value)
    if end_value is None and not use_start_precision_for_implicit_end:
        end_date = _derive_end(start_date, precision, available_end.isoformat(), available_end)
    else:
        end_date = _derive_end(start_date, precision, end_value, available_end)
    return DateRange(start=start_date, end=end_date)
