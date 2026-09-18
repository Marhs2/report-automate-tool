import unittest
from datetime import date

from kr_holidays import kr_holiday_map, kr_holiday_name
from main import _missing_weekdays


class KrHolidayMapTests(unittest.TestCase):
    def test_constitution_day_is_not_treated_as_rest_day(self):
        holidays = kr_holiday_map(2026)
        self.assertNotIn("2026-07-17", holidays)
        self.assertIsNone(kr_holiday_name(date(2026, 7, 17)))

    def test_weekday_substitute_holiday_is_present(self):
        holidays = kr_holiday_map(2026)
        self.assertEqual(holidays["2026-03-02"], "삼일절 대체 휴일")

    def test_labor_day_is_present(self):
        holidays = kr_holiday_map(2026)
        self.assertIn("2026-05-01", holidays)

    def test_chuseok_weekdays_are_holidays(self):
        holidays = kr_holiday_map(2026)
        self.assertIn("2026-09-24", holidays)
        self.assertIn("2026-09-25", holidays)


class MissingWeekdaysTests(unittest.TestCase):
    def test_weekday_holiday_is_not_listed_as_missing(self):
        missing = _missing_weekdays(
            ["2026-09-21", "2026-09-22", "2026-09-23"]
        )
        self.assertEqual(missing, [])

    def test_constitution_day_friday_still_counts_as_missing(self):
        missing = _missing_weekdays(["2026-07-13"])
        self.assertIn("2026-07-17", missing)


if __name__ == "__main__":
    unittest.main()
