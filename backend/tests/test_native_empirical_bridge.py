from __future__ import annotations

from pathlib import Path
import pytest

from app.native_empirical_bridge import NativeEmpiricalError, native_empirical_latency


def test_no_empirical_data_does_not_claim_trained_cost(monkeypatch):
    monkeypatch.delenv("MORPHEUS_EMPIRICAL_COST_TRAINING_FILE", raising=False)
    assert native_empirical_latency("bitmap", "filter", 100, 5, 0.2, 0) is None


def test_configured_native_model_fails_closed_if_binary_missing(monkeypatch, tmp_path):
    measurements = tmp_path / "measurements.txt"
    measurements.write_text("MORPHEUS_EMPIRICAL_COST_V1\n1\nbitmap filter 100 5 0.2 0 0.1\n")
    monkeypatch.setenv("MORPHEUS_EMPIRICAL_COST_TRAINING_FILE", str(measurements))
    monkeypatch.setenv("MORPHEUS_EMPIRICAL_COST_EXECUTABLE", str(tmp_path / "missing"))
    with pytest.raises(NativeEmpiricalError, match="without a C\\+\\+20 executable"):
        native_empirical_latency("bitmap", "filter", 100, 5, 0.2, 0)


def test_missing_training_coverage_returns_no_ml_prediction(monkeypatch, tmp_path):
    import os
    executable = os.getenv("MORPHEUS_EMPIRICAL_COST_EXECUTABLE", "")
    if not executable or not Path(executable).is_file():
        pytest.skip("requires compiled C++20 ML executable")
    measurements = tmp_path / "measurements.txt"
    measurements.write_text("MORPHEUS_EMPIRICAL_COST_V1\n1\nbitmap filter 100 5 0.2 0 0.1\n")
    monkeypatch.setenv("MORPHEUS_EMPIRICAL_COST_TRAINING_FILE", str(measurements))
    assert native_empirical_latency("bitmap", "filter", 100, 5, 0.2, 0) is None
