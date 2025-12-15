from datetime import date
import unittest

from slurm_cli.dates import DateRangeError, resolve_date_range


class DateRangeTests(unittest.TestCase):
    def test_resolve_year_defaults_to_full_year(self):
        rng = resolve_date_range("2024", None)
        self.assertEqual(rng.start, date(2024, 1, 1))
        self.assertEqual(rng.end, date(2024, 12, 31))
        self.assertEqual(rng.days(), 366)

    def test_resolve_month_defaults_to_end_of_month(self):
        rng = resolve_date_range("2024-02", None)
        self.assertEqual(rng.start, date(2024, 2, 1))
        self.assertEqual(rng.end, date(2024, 2, 29))
        self.assertEqual(rng.days(), 29)

    def test_resolve_exact_date_defaults_to_month_end(self):
        rng = resolve_date_range("2024-03-15", None)
        self.assertEqual(rng.start, date(2024, 3, 15))
        self.assertEqual(rng.end, date(2024, 3, 31))
        self.assertEqual(rng.days(), 17)

    def test_invalid_start_raises_error(self):
        with self.assertRaises(DateRangeError):
            resolve_date_range("2024-13", None)

    def test_end_before_start_raises_error(self):
        with self.assertRaises(DateRangeError):
            resolve_date_range("2024-03", "2024-02-01")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
