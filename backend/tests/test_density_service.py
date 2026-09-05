"""Business-logic tests for DensityService.calculate() and classify()."""

import pytest


@pytest.fixture()
def service(monkeypatch, tmp_path):
    from app.core.config import get_settings

    monkeypatch.setenv("MODEL_DIR", str(tmp_path))
    # Pin capacities so assertions are stable regardless of env.
    monkeypatch.setenv("DEFAULT_LANE_CAPACITY", "50")
    monkeypatch.setenv("HIGHWAY_LANE_CAPACITY", "80")
    monkeypatch.setenv("SERVICE_ROAD_CAPACITY", "25")
    get_settings.cache_clear()
    from app.services.density_service import DensityService

    svc = DensityService()
    yield svc
    get_settings.cache_clear()


# --- calculate() ---------------------------------------------------------

def test_calculate_urban(service):
    # 100 vehicles, 2 lanes, urban (50/lane) -> capacity 100 -> density 1.0
    assert service.calculate(100, lanes=2, road_type="urban") == 1.0
    # 50 vehicles, 2 lanes urban -> 50/100 = 0.5
    assert service.calculate(50, lanes=2, road_type="urban") == 0.5


def test_calculate_highway(service):
    # 80 vehicles, 1 lane, highway (80/lane) -> capacity 80 -> density 1.0
    assert service.calculate(80, lanes=1, road_type="highway") == 1.0
    # 40 vehicles, 1 lane highway -> 40/80 = 0.5
    assert service.calculate(40, lanes=1, road_type="highway") == 0.5


def test_calculate_service(service):
    # 25 vehicles, 1 lane, service (25/lane) -> capacity 25 -> density 1.0
    assert service.calculate(25, lanes=1, road_type="service") == 1.0
    # 5 vehicles, 1 lane service -> 5/25 = 0.2
    assert service.calculate(5, lanes=1, road_type="service") == 0.2


def test_calculate_capped_at_one(service):
    # Over capacity clamps to 1.0.
    assert service.calculate(500, lanes=1, road_type="urban") == 1.0


def test_calculate_lanes_none_defaults_to_one(service):
    # lanes=None -> treated as 1 lane. 25/50 = 0.5 urban.
    assert service.calculate(25, lanes=None, road_type="urban") == 0.5


def test_calculate_lanes_zero_treated_as_one(service):
    # lanes=0 -> max(0 or 1, 1) = 1 lane, no ZeroDivisionError.
    assert service.calculate(25, lanes=0, road_type="urban") == 0.5


def test_calculate_unknown_road_type_uses_urban_capacity(service):
    # Unknown road type falls back to default (urban) capacity.
    assert service.calculate(50, lanes=2, road_type="mystery") == 0.5


# --- classify() : four avg_speed override branches + density fallback ----

def test_classify_speed_below_10_is_critical(service):
    # avg_speed < 10 -> critical regardless of (low) density.
    assert service.classify(density=0.05, avg_speed=5.0) == "critical"


def test_classify_speed_below_20_with_density_ge_030_is_high(service):
    # avg_speed < 20 AND density >= 0.3 -> high.
    assert service.classify(density=0.35, avg_speed=15.0) == "high"


def test_classify_speed_above_50_low_density_is_low(service):
    # avg_speed > 50 AND density < 0.4 -> low (free flow), even if density would
    # otherwise be "moderate".
    assert service.classify(density=0.35, avg_speed=60.0) == "low"


def test_classify_density_fallback_when_speed_does_not_trigger(service):
    # avg_speed present but none of the override thresholds trigger
    # (25 km/h, density 0.9) -> density fallback -> critical (>= 0.8).
    assert service.classify(density=0.9, avg_speed=25.0) == "critical"
    # avg_speed provided, 25 km/h, density 0.6 -> fallback -> high (>=0.55).
    assert service.classify(density=0.6, avg_speed=25.0) == "high"


def test_classify_pure_density_fallback_no_speed(service):
    # No avg_speed at all -> pure density thresholds.
    assert service.classify(density=0.85) == "critical"
    assert service.classify(density=0.6) == "high"
    assert service.classify(density=0.4) == "moderate"
    assert service.classify(density=0.1) == "low"


def test_classify_speed_below_20_but_low_density_falls_through(service):
    # avg_speed < 20 but density < 0.3 -> the < 20 branch does NOT trigger,
    # falls through to density fallback -> low.
    assert service.classify(density=0.1, avg_speed=15.0) == "low"
