from __future__ import annotations

import textwrap

import pytest

from app.parser import parse_workload_text
from app.search_quality import compare_beam_to_exhaustive


SPEC = textwrap.dedent(
    """
    version: mws-0.1
    name: search_quality_demo
    record_count: 25000
    fields:
      - name: id
        type: uint64
        cardinality: 25000
      - name: age
        type: uint32
        cardinality: 100
      - name: city
        type: string
        cardinality: 250
    queries:
      - kind: point_lookup
        field: id
        weight: 0.45
      - kind: range_scan
        field: age
        weight: 0.25
        selectivity: 0.05
      - kind: filter
        field: city
        weight: 0.20
        selectivity: 0.03
      - kind: point_lookup
        field: id
        weight: 0.10
    constraints:
      memory_mb: 64
    objective:
      latency: 1.0
      memory: 0.15
      update: 0.2
      build: 0.05
    """
).strip()


def test_beam_quality_report_is_bounded_and_uses_model_oracle() -> None:
    report = compare_beam_to_exhaustive(parse_workload_text(SPEC), beam_width=4, exhaustive_limit=10000)

    assert report.theoretical_configurations >= report.exhaustive_evaluated
    assert report.exhaustive_evaluated > 0
    assert 0 < report.beam_evaluated <= 4
    assert 0 <= report.search_reduction_ratio <= 1
    assert report.evidence_state == "SEARCH_HEURISTIC_EVALUATED_AGAINST_EXHAUSTIVE_MODEL_ORACLE"
    if report.absolute_score_regret is not None:
        assert report.absolute_score_regret >= 0
    if report.pareto_id_coverage_ratio is not None:
        assert 0 <= report.pareto_id_coverage_ratio <= 1


def test_search_quality_refuses_a_truncated_exhaustive_oracle() -> None:
    with pytest.raises(ValueError, match="exhaustive oracle would be truncated"):
        compare_beam_to_exhaustive(parse_workload_text(SPEC), beam_width=2, exhaustive_limit=1)
