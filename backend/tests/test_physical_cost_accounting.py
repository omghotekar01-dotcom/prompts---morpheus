from __future__ import annotations

import pytest

from app.engine import synthesize
from app.models import FieldSpec, QueryKind, QuerySpec, WorkloadSpec


def test_repeated_primitive_routes_are_not_deduplicated_in_memory_or_update_cost() -> None:
    spec = WorkloadSpec(
        name="two_hash_routes",
        record_count=10_000,
        fields=[FieldSpec(name="id", type="uint64", cardinality=10_000)],
        queries=[
            QuerySpec(kind=QueryKind.POINT_LOOKUP, field="id", weight=1.0),
            QuerySpec(kind=QueryKind.POINT_LOOKUP, field="id", weight=1.0),
        ],
    )

    result = synthesize(spec)
    assert result.winner is not None
    assert [assignment.primitive for assignment in result.winner.assignments] == [
        "robin_hood_hash",
        "robin_hood_hash",
    ]
    assert result.winner.unique_primitives == ["robin_hood_hash"]

    # The generated artifact contains two physical hash members even though the
    # primitive family is the same. Memory/build/update accounting must charge
    # both members rather than collapsing them through set(unique_primitives).
    expected_memory_mb = (2 * 36.0 * spec.record_count) / (1024 * 1024)
    assert result.winner.predicted_memory_mb == pytest.approx(expected_memory_mb, abs=1e-6)
    assert result.winner.predicted_update_us == pytest.approx(2 * 0.17, abs=1e-6)
    assert any("index members per query route" in warning for warning in result.warnings)


def test_mutation_declaration_does_not_add_a_physical_member_charge() -> None:
    spec = WorkloadSpec(
        name="point_plus_update_signal",
        record_count=10_000,
        fields=[FieldSpec(name="id", type="uint64", cardinality=10_000)],
        queries=[
            QuerySpec(kind=QueryKind.POINT_LOOKUP, field="id", weight=0.8),
            QuerySpec(kind=QueryKind.UPDATE, weight=0.2),
        ],
    )

    result = synthesize(spec)
    assert result.winner is not None
    # Only the point route materializes a generated index. The UPDATE entry is a
    # workload/cost signal and generated mutations maintain the point index.
    expected_memory_mb = (36.0 * spec.record_count) / (1024 * 1024)
    assert result.winner.predicted_memory_mb == pytest.approx(expected_memory_mb, abs=1e-6)
    assert result.winner.predicted_update_us == pytest.approx(0.17, abs=1e-6)
    assert any("Mutation declarations are cost-model workload signals" in warning for warning in result.warnings)
