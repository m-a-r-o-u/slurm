from datetime import date
import unittest

from slurm_cli.dates import DateRangeError, resolve_date_range


class DateRangeTests(unittest.TestCase):
    def test_resolve_year_defaults_to_full_year(self):
        rng = resolve_date_range("2024", None, reference_date=date(2025, 1, 2))
        self.assertEqual(rng.start, date(2024, 1, 1))
        self.assertEqual(rng.end, date(2024, 12, 31))
        self.assertEqual(rng.days(), 366)

    def test_resolve_month_defaults_to_end_of_month(self):
        rng = resolve_date_range("2024-02", None, reference_date=date(2024, 3, 1))
        self.assertEqual(rng.start, date(2024, 2, 1))
        self.assertEqual(rng.end, date(2024, 2, 29))
        self.assertEqual(rng.days(), 29)

    def test_resolve_exact_date_defaults_to_month_end(self):
        rng = resolve_date_range("2024-03-15", None, reference_date=date(2024, 3, 20))
        self.assertEqual(rng.start, date(2024, 3, 15))
        self.assertEqual(rng.end, date(2024, 3, 15))
        self.assertEqual(rng.days(), 1)

    def test_truncates_to_available_date_for_current_month(self):
        rng = resolve_date_range("2024-04", None, reference_date=date(2024, 4, 10))
        self.assertEqual(rng.start, date(2024, 4, 1))
        self.assertEqual(rng.end, date(2024, 4, 9))
        self.assertEqual(rng.days(), 9)

    def test_resolve_last_days(self):
        rng = resolve_date_range("lastD:5", None, reference_date=date(2024, 6, 15))
        self.assertEqual(rng.start, date(2024, 6, 10))
        self.assertEqual(rng.end, date(2024, 6, 14))
        self.assertEqual(rng.days(), 5)

    def test_resolve_last_months(self):
        rng = resolve_date_range("lastM:2", None, reference_date=date(2024, 6, 15))
        self.assertEqual(rng.start, date(2024, 5, 1))
        self.assertEqual(rng.end, date(2024, 6, 14))

    def test_invalid_relative_selector(self):
        with self.assertRaises(DateRangeError):
            resolve_date_range("lastD:0", None, reference_date=date(2024, 6, 15))

    def test_invalid_start_raises_error(self):
        with self.assertRaises(DateRangeError):
            resolve_date_range("2024-13", None)

    def test_end_before_start_raises_error(self):
        with self.assertRaises(DateRangeError):
            resolve_date_range("2024-03", "2024-02-01")

    def test_start_after_available_end_raises_error(self):
        with self.assertRaises(DateRangeError):
            resolve_date_range("2024-05-10", None, reference_date=date(2024, 5, 5))

    def test_start_can_extend_to_available_end_when_requested(self):
        rng = resolve_date_range(
            "2025",
            None,
            reference_date=date(2026, 6, 15),
            use_start_precision_for_implicit_end=False,
        )
        self.assertEqual(rng.start, date(2025, 1, 1))
        self.assertEqual(rng.end, date(2026, 6, 14))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
