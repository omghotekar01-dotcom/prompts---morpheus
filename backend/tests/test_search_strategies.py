from __future__ import annotations

from app.models import SearchStrategy
from app.parser import parse_workload_text
from app.search_quality import (
    compare_beam_to_exhaustive,
    compare_greedy_to_exhaustive,
    compare_strategy_to_exhaustive,
)


SPEC = """
version: mws-0.1
name: search_strategy_quality
record_count: 10000
fields:
  - name: id
    type: uint64
    cardinality: 10000
queries:
  - kind: point_lookup
    field: id
    weight: 0.25
  - kind: point_lookup
    field: id
    weight: 0.20
  - kind: point_lookup
    field: id
    weight: 0.20
  - kind: point_lookup
    field: id
    weight: 0.15
  - kind: point_lookup
    field: id
    weight: 0.10
  - kind: point_lookup
    field: id
    weight: 0.10
constraints:
  memory_mb: 64
""".strip()


def test_greedy_quality_report_is_bounded_model_oracle_comparison() -> None:
    spec = parse_workload_text(SPEC)
    report = compare_greedy_to_exhaustive(spec, exhaustive_limit=10_000)
    assert report.heuristic_strategy == "greedy"
    assert report.heuristic_evaluated == 1
    assert report.exhaustive_evaluated > report.heuristic_evaluated
    assert 0.0 <= report.search_reduction_ratio < 1.0
    assert report.evidence_state == "SEARCH_HEURISTIC_EVALUATED_AGAINST_EXHAUSTIVE_MODEL_ORACLE"
    payload = report.as_dict()
    assert payload["heuristic_strategy"] == "greedy"
    assert "beam_evaluated" not in payload


def test_beam_wrapper_preserves_backward_compatible_fields() -> None:
    spec = parse_workload_text(SPEC)
    report = compare_beam_to_exhaustive(spec, beam_width=8, exhaustive_limit=10_000)
    assert report.heuristic_strategy == "beam"
    assert report.beam_evaluated == report.heuristic_evaluated
    assert report.beam_winner_id == report.heuristic_winner_id
    payload = report.as_dict()
    assert payload["beam_evaluated"] == payload["heuristic_evaluated"]
    assert payload["beam_winner_id"] == payload["heuristic_winner_id"]


def test_search_quality_rejects_non_heuristic_strategy() -> None:
    spec = parse_workload_text(SPEC)
    try:
        compare_strategy_to_exhaustive(
            spec,
            strategy=SearchStrategy.EXHAUSTIVE,
            exhaustive_limit=10_000,
        )
    except ValueError as exc:
        assert "greedy or beam" in str(exc)
    else:
        raise AssertionError("exhaustive strategy must not be accepted as the heuristic side")
