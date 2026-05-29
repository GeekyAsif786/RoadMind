from pathlib import Path


def test_emergency_direction_aliases_normalize_to_signal_codes() -> None:
    from app.services.optimization_service import SignalOptimizationService

    service = SignalOptimizationService.__new__(SignalOptimizationService)

    assert service._normalize_signal_direction("northbound") == "N"
    assert service._normalize_signal_direction("south west") == "SW"
    assert service._normalize_signal_direction("unknown-lane") == "ALL"


def test_security_headers_include_operator_safe_defaults() -> None:
    from app.core.security import security_headers

    headers = security_headers()

    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert "camera=()" in headers["Permissions-Policy"]


def test_xgboost_strategy_can_be_selected(monkeypatch, tmp_path: Path) -> None:
    from app.core.config import get_settings
    from app.ml.traffic_predictor import TrafficPredictor

    monkeypatch.setenv("TRAFFIC_MODEL", "xgboost")
    monkeypatch.setenv("MODEL_DIR", str(tmp_path))
    get_settings.cache_clear()

    predictor = TrafficPredictor()

    assert predictor.strategy.model_key == "xgboost"
    assert predictor.strategy.build_model() is not None

    get_settings.cache_clear()
