"""Regression coverage for the MORPHEUS workload-input evidence boundary."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.parser import SpecParseError, parse_workload_document, parse_workload_text


VALID = """
name: valid_input
fields:
  - name: id
    type: uint64
  - name: label
    type: string
queries:
  - kind: point_lookup
    field: id
    weight: 1.0
""".strip()


@pytest.mark.parametrize(
    "raw",
    [
        VALID + "\nrecord_count: 1000\nrecord_count: 2000",
        VALID.replace("    weight: 1.0", "    weight: 1.0\n    weight: 0.1"),
        VALID.replace("    type: string", "    type: string\n    type: uint64"),
        '{"fields":[{"name":"id","type":"uint64"}],'
        '"queries":[{"kind":"point_lookup","field":"id"}],'
        '"record_count":1000,"record_count":2000}',
    ],
)
def test_duplicate_keys_are_rejected_not_silently_overridden(raw: str) -> None:
    with pytest.raises(SpecParseError, match="duplicate mapping key"):
        parse_workload_text(raw)


@pytest.mark.parametrize(
    "raw",
    [
        VALID.replace("    weight: 1.0", "    weight: .inf"),
        VALID.replace("    weight: 1.0", "    weight: .nan"),
        VALID + "\nconstraints:\n  memory_mb: .inf",
        VALID + "\nconstraints:\n  update_rate: .inf",
        VALID + "\nobjective:\n  latency: .inf",
        VALID.replace("    weight: 1.0", "    weight: 1.0\n    distribution:\n      kind: zipf\n      zipf_theta: .inf"),
    ],
)
def test_non_finite_workload_numbers_are_rejected(raw: str) -> None:
    with pytest.raises(SpecParseError):
        parse_workload_text(raw)


def test_identical_keys_in_distinct_objects_remain_allowed() -> None:
    document = parse_workload_document(VALID)
    assert [field.name for field in document.resolved_spec.fields] == ["id", "label"]
    assert document.resolved_spec.queries[0].weight == 1.0


def test_input_integrity_failures_surface_as_validation_errors() -> None:
    client = TestClient(app)
    invalid = VALID.replace("    weight: 1.0", "    weight: 1.0\n    weight: 2.0")
    response = client.post("/api/validate", json={"spec_text": invalid})
    assert response.status_code == 422
    assert "duplicate mapping key" in response.json()["detail"]
