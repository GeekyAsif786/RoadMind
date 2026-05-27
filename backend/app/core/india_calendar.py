from datetime import date
from functools import lru_cache


@lru_cache(maxsize=None)
def _get_calendar():
    try:
        from workalendar.asia import India

        return India()
    except ImportError:
        return None


def is_indian_holiday(d: date) -> int:
    cal = _get_calendar()
    if cal is None:
        return 0
    try:
        return 1 if cal.is_holiday(d) else 0
    except Exception:
        return 0
