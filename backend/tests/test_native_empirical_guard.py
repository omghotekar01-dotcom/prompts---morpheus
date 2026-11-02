from __future__ import annotations

import pytest

from app import cost_model
from app.models import WorkloadSpec
from app.native_empirical_bridge import NativeEmpiricalError


@pytest.fixture(autouse=True)
def no_other_cost_evidence(monkeypatch):
    monkeypatch.setattr(cost_model.CALIBRATIONS, "active", lambda: None)
    monkeypatch.delenv("MORPHEUS_REQUIRE_EMPIRICAL_COST", raising=False)


def _spec(with_selectivity: bool):
    route = {"kind": "filter", "field": "warehouse", "weight": 1}
    if with_selectivity:
        route["selectivity"] = 0.25
    return WorkloadSpec.model_validate({
        "record_count": 1000,
        "fields": [{"name": "warehouse", "type": "string", "cardinality": 4}],
        "queries": [route],
    })


def test_unspecified_selectivity_is_not_passed_to_cpp_ml(monkeypatch):
    workload = _spec(False)
    assert workload.queries[0].selectivity_defaulted
    monkeypatch.setattr(cost_model, "native_empirical_latency",
                        lambda *args: pytest.fail("ML must not use imputed selectivity"))
    estimate = cost_model.estimate_query_latency_us(workload, workload.queries[0], "bitmap")
    assert estimate.source.startswith("BOOTSTRAP_PRIOR")


def test_strict_empirical_mode_refuses_imputed_selectivity(monkeypatch):
    workload = _spec(False)
    monkeypatch.setenv("MORPHEUS_REQUIRE_EMPIRICAL_COST", "1")
    monkeypatch.setattr(cost_model, "native_empirical_latency",
                        lambda *args: pytest.fail("ML must not use imputed selectivity"))
    with pytest.raises(NativeEmpiricalError, match="unavailable"):
        cost_model.estimate_query_latency_us(workload, workload.queries[0], "bitmap")


def test_explicit_selectivity_may_use_native_model(monkeypatch):
    workload = _spec(True)
    assert not workload.queries[0].selectivity_defaulted
    monkeypatch.setattr(cost_model, "native_empirical_latency",
                        lambda *args: (0.14, 0.01, 20, "abc123"))
    estimate = cost_model.estimate_query_latency_us(workload, workload.queries[0], "bitmap")
    assert estimate.value == 0.14
    assert estimate.source.startswith("NATIVE_CPP_LEARNED_USER_MEASUREMENTS")
