import argparse
from datetime import date
import unittest

from slurm_cli.cli import _resolve_date_range_from_args


class ResolveDateRangeFromArgsTests(unittest.TestCase):
    def test_prefers_date_argument(self):
        args = argparse.Namespace(date="2024", start=None, end=None, reference_date=date(2025, 1, 2))
        rng = _resolve_date_range_from_args(args)
        self.assertEqual(rng.start, date(2024, 1, 1))
        self.assertEqual(rng.end, date(2024, 12, 31))

    def test_uses_start_and_end_when_provided(self):
        args = argparse.Namespace(
            date=None, start="2024-03-01", end="2024-03-10", reference_date=date(2024, 12, 31)
        )
        rng = _resolve_date_range_from_args(args)
        self.assertEqual(rng.start, date(2024, 3, 1))
        self.assertEqual(rng.end, date(2024, 3, 10))

    def test_start_without_end_uses_latest_available_date(self):
        args = argparse.Namespace(date=None, start="2025", end=None, reference_date=date(2026, 7, 1))
        rng = _resolve_date_range_from_args(args)
        self.assertEqual(rng.start, date(2025, 1, 1))
        self.assertEqual(rng.end, date(2026, 6, 30))

    def test_missing_date_values_raise(self):
        args = argparse.Namespace(date=None, start=None, end=None, reference_date=date(2024, 1, 1))
        with self.assertRaises(SystemExit):
            _resolve_date_range_from_args(args)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
