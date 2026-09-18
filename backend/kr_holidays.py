import sys
from datetime import date
from pathlib import Path

_vendor = Path(__file__).resolve().parent / ".vendor"
if _vendor.is_dir() and str(_vendor) not in sys.path:
    sys.path.insert(0, str(_vendor))

import holidays

_cache = {}

# 국경일이지만 관공서·일반 근무일은 쉬는 날이 아니다.
_SKIP_HOLIDAY_MARKERS = ("제헌절",)


def _is_rest_day_name(name):
    text = str(name or "")
    return bool(text) and not any(marker in text for marker in _SKIP_HOLIDAY_MARKERS)


def kr_holiday_map(*years):
    years = tuple(sorted({int(year) for year in years if year is not None}))
    if not years:
        years = (date.today().year,)
    cached = _cache.get(years)
    if cached is None:
        calendar = holidays.KR(years=list(years), language="ko")
        cached = {
            day.isoformat(): name
            for day, name in sorted(calendar.items())
            if _is_rest_day_name(name)
        }
        _cache[years] = cached
    return cached


def kr_holiday_name(value):
    if isinstance(value, date):
        day = value
    else:
        try:
            day = date.fromisoformat(str(value)[:10])
        except ValueError:
            return None
    return kr_holiday_map(day.year).get(day.isoformat())
