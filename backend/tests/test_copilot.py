from __future__ import annotations

from app.copilot import answer_from_run
from app.engine import synthesize
from app.parser import parse_workload_text


SPEC = """
version: mws-0.1
name: copilot_test
record_count: 1000
fields:
  - name: id
    type: uint64
    cardinality: 1000
queries:
  - kind: point_lookup
    field: id
    weight: 1.0
constraints:
  memory_mb: 16
""".strip()


def _run_record():
    spec = parse_workload_text(SPEC)
    result = synthesize(spec)
    return {
        "run_id": "run-test",
        "spec_hash": result.spec_hash,
        "result": result.model_dump(mode="json"),
    }


def test_copilot_grounds_why_answer_in_run_evidence() -> None:
    response = answer_from_run(_run_record(), "Why did MORPHEUS choose this winner?")
    assert response.mode == "DETERMINISTIC_EVIDENCE"
    assert response.confidence == "HIGH"
    assert "lowest-score feasible" in response.answer
    assert any(ref.startswith("candidate:") for ref in response.evidence_refs)


def test_copilot_never_converts_prediction_into_measurement_claim() -> None:
    response = answer_from_run(_run_record(), "Is this benchmark measured real speed?")
    assert "bootstrap model predictions" in response.answer
    assert "not measurements" in response.answer
