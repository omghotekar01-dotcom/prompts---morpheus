from __future__ import annotations

from app.engine import synthesize
from app.index_footprint import predicted_index_bytes
from app.models import Constraints, FieldSpec, QueryKind, QuerySpec, SearchStrategy, WorkloadSpec


def _model(cardinality: int) -> WorkloadSpec:
    return WorkloadSpec(
        name="completely_arbitrary_catalog",
        record_count=1000,
        fields=[FieldSpec(name="Whatever_Field", type="string", cardinality=cardinality)],
        queries=[
            QuerySpec(
                kind=QueryKind.FILTER,
                field="Whatever_Field",
                selectivity=(1 / cardinality),
                weight=1.0,
            )
        ],
        constraints=Constraints(memory_mb=0.03),
    )


def test_real_column_cardinality_changes_memory_and_feasible_winner() -> None:
    few_distinct = _model(2)
    many_distinct = _model(1000)
    assert predicted_index_bytes(few_distinct, "bitmap", "Whatever_Field") == 2596.0
    assert predicted_index_bytes(many_distinct, "bitmap", "Whatever_Field") == 50500.0
    assert predicted_index_bytes(few_distinct, "sorted_array", "Whatever_Field") == 20000.0
    low = synthesize(few_distinct, strategy=SearchStrategy.EXHAUSTIVE)
    high = synthesize(many_distinct, strategy=SearchStrategy.EXHAUSTIVE)
    assert low.winner is not None and low.winner.assignments[0].primitive == "bitmap"
    assert high.winner is not None and high.winner.assignments[0].primitive == "sorted_array"
    rejected = {a.assignments[0].primitive: a for a in high.candidates}
    assert not rejected["bitmap"].feasible
    assert "exceeds hard limit" in rejected["bitmap"].rejection_reasons[0]
    assert high.search_summary.evaluated_configurations == 3
