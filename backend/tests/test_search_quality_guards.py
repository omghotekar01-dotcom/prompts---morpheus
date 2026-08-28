from __future__ import annotations

import pytest

from app.models import SearchStrategy
from app.parser import parse_workload_text
from app.search_quality import compare_strategy_to_exhaustive


SPEC = """
version: mws-0.1
name: search_quality_guards
record_count: 10000
fields:
  - name: id
    type: uint64
    cardinality: 10000
queries:
  - kind: point_lookup
    field: id
    weight: 1.0
constraints:
  memory_mb: 64
""".strip()


def test_search_quality_rejects_invalid_bounds_before_synthesis() -> None:
    spec = parse_workload_text(SPEC)

    with pytest.raises(ValueError, match="beam_width must be positive"):
        compare_strategy_to_exhaustive(
            spec,
            strategy=SearchStrategy.BEAM,
            beam_width=0,
            exhaustive_limit=100,
        )

    with pytest.raises(ValueError, match="exhaustive_limit must be positive"):
        compare_strategy_to_exhaustive(
            spec,
            strategy=SearchStrategy.GREEDY,
            exhaustive_limit=0,
        )


def test_search_quality_refuses_a_truncated_exhaustive_oracle() -> None:
    spec = parse_workload_text(SPEC)

    with pytest.raises(ValueError, match="exhaustive oracle would be truncated"):
        compare_strategy_to_exhaustive(
            spec,
            strategy=SearchStrategy.GREEDY,
            exhaustive_limit=1,
        )
