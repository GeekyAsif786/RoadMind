"""Business-logic tests for SignalOptimizationService._green_time().

_green_time reads the current month (monsoon floor) and the current IST hour
(peak bonus / night reduction) from the clock, so the tests patch both the
module-level ``datetime`` class and ``dt`` module with a fake fixed clock.

Config assumptions (pinned via env in the fixture):
    min_green_seconds = 15, max_green_seconds = 90  -> span = 75
Weather multipliers: clear 1.0, light_rain 1.15, heavy_rain 1.35, fog 1.25.
"""

import datetime as real_dt

import pytest

import app.services.optimization_service as opt


@pytest.fixture()
def service(monkeypatch, tmp_path):
    from app.core.config import get_settings

    monkeypatch.setenv("MODEL_DIR", str(tmp_path))
    monkeypatch.setenv("MIN_GREEN_SECONDS", "15")
    monkeypatch.setenv("MAX_GREEN_SECONDS", "90")
    get_settings.cache_clear()
    from app.services.optimization_service import SignalOptimizationService

    # Build without touching the DB.
    svc = SignalOptimizationService.__new__(SignalOptimizationService)
    svc.settings = get_settings()
    yield svc
    get_settings.cache_clear()


def _install_fake_clock(monkeypatch, *, month, ist_hour):
    """Patch optimization_service so 'now' returns a fixed month/hour.

    _green_time calls:
      dt.datetime.now(dt.UTC).month        -> month
      datetime.now(IST).hour               -> ist_hour
    We return a datetime whose .month is `month`; for the IST call we return one
    whose .hour is `ist_hour`. A single fake with both fields set satisfies both
    because .month and .hour are independent attributes.
    """
    fixed = real_dt.datetime(2026, month, 15, ist_hour, 0, 0, tzinfo=real_dt.UTC)

    class _FakeDateTime(real_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed

    # Patch the `datetime` name (used as datetime.now(IST)).
    monkeypatch.setattr(opt, "datetime", _FakeDateTime)

    # Patch the `dt` module's datetime (used as dt.datetime.now(dt.UTC).month).
    class _FakeDtModule:
        datetime = _FakeDateTime
        UTC = real_dt.UTC

    monkeypatch.setattr(opt, "dt", _FakeDtModule)


def test_weather_multiplier_stacking(service, monkeypatch):
    # Neutral clock: April (non-monsoon), 14:00 IST (not peak, not night).
    _install_fake_clock(monkeypatch, month=4, ist_hour=14)

    # density 0.5 -> base = 15 + 0.5*75 = 52 (int truncation of 52.5).
    clear = service._green_time(0.5, "clear")
    assert clear == 52

    # heavy_rain multiplier 1.35 -> int(52*1.35)=int(70.2)=70.
    heavy = service._green_time(0.5, "heavy_rain")
    assert heavy == 70

    # light_rain 1.15 -> int(52*1.15)=int(59.8)=59.
    light = service._green_time(0.5, "light_rain")
    assert light == 59

    assert heavy > light > clear  # multiplier stacks on top of base


def test_monsoon_month_floor(service, monkeypatch):
    # July (monsoon), neutral hour. Very low density -> base below the floor.
    _install_fake_clock(monkeypatch, month=7, ist_hour=14)
    # density 0.0 -> base = 15, clear multiplier -> 15, monsoon floor raises to 25.
    assert service._green_time(0.0, "clear") == 25

    # Non-monsoon month with the same inputs stays at 15 (no floor).
    _install_fake_clock(monkeypatch, month=4, ist_hour=14)
    assert service._green_time(0.0, "clear") == 15


def test_peak_bonus_vs_night_reduction(service, monkeypatch):
    # density 0.4 -> base = 15 + 0.4*75 = 45.
    # Morning peak (08:00 IST) -> +15 -> 60.
    _install_fake_clock(monkeypatch, month=4, ist_hour=8)
    assert service._green_time(0.4, "clear") == 60

    # Night (02:00 IST) -> -10 -> 35.
    _install_fake_clock(monkeypatch, month=4, ist_hour=2)
    assert service._green_time(0.4, "clear") == 35

    # Evening peak (18:00 IST) -> +15 -> 60.
    _install_fake_clock(monkeypatch, month=4, ist_hour=18)
    assert service._green_time(0.4, "clear") == 60


def test_max_green_is_hard_ceiling_when_weather_and_peak_stack(service, monkeypatch):
    # High density + heavy rain + morning peak should never exceed max_green (90).
    _install_fake_clock(monkeypatch, month=7, ist_hour=8)  # monsoon + peak
    result = service._green_time(1.0, "heavy_rain")
    # base = 15 + 1.0*75 = 90; *1.35 -> capped at 90; monsoon floor <= 90;
    # peak +15 -> min(105, 90) = 90.
    assert result == 90
    assert result <= service.settings.max_green_seconds


def test_night_reduction_floored_at_min_green(service, monkeypatch):
    # Very low density at night must not drop below min_green (15).
    _install_fake_clock(monkeypatch, month=4, ist_hour=3)
    result = service._green_time(0.0, "clear")
    assert result == service.settings.min_green_seconds == 15
