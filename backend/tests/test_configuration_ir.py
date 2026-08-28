from __future__ import annotations

from app.catalog import PRIMITIVES
from app.configuration_ir import (
    CONFIGURATION_IR_VERSION,
    configuration_ir_hash,
    lower_configuration_ir,
)
from app.engine import synthesize
from app.parser import parse_workload_text


SPEC = """
version: mws-0.1
name: config_ir_demo
record_count: 10000
fields:
  - name: id
    type: uint64
    cardinality: 10000
  - name: age
    type: uint32
    cardinality: 100
  - name: name
    type: string
    cardinality: 5000
  - name: team
    type: string
    cardinality: 20
queries:
  - kind: point_lookup
    field: id
    weight: 0.25
  - kind: range_scan
    field: age
    weight: 0.25
    selectivity: 0.1
  - kind: prefix_search
    field: name
    weight: 0.25
  - kind: filter
    field: team
    weight: 0.25
constraints:
  memory_mb: 128
""".strip()


def test_configuration_ir_binds_workload_catalog_routes_and_cost_vector() -> None:
    spec = parse_workload_text(SPEC)
    result = synthesize(spec)
    assert result.winner is not None

    first = lower_configuration_ir(spec, result.winner)
    second = lower_configuration_ir(parse_workload_text(SPEC), result.winner.model_copy(deep=True))
    assert first == second
    assert first.ir_version == CONFIGURATION_IR_VERSION
    assert CONFIGURATION_IR_VERSION == "morpheus-configuration-ir-v2"
    assert len(first.workload_ir_hash) == 64
    assert len(first.primitive_manifest_hash) == 64
    assert configuration_ir_hash(first) == configuration_ir_hash(second)
    assert first.candidate_id == result.winner.id
    assert first.cost.predicted_memory_mb == result.winner.predicted_memory_mb
    assert all(route.materializes_structure for route in first.routes)
    assert all(route.implementation_id == PRIMITIVES[route.primitive].implementation_id for route in first.routes)

    policies = {route.query_kind.value: route.physical_key_policy for route in first.routes}
    assert policies["point_lookup"] == "logical_key_to_last_live_stable_slot_winner"
    assert policies["range_scan"] == "logical_key_stable_slot_pair"
    assert policies["prefix_search"] == "string_key_to_duplicate_preserving_stable_slot_postings"
    assert policies["filter"] == "logical_value_to_all_stable_slot_postings"
    assert len({route.structure_id for route in first.routes}) == len(first.routes)


def test_configuration_hash_changes_with_candidate_or_workload_semantics() -> None:
    spec = parse_workload_text(SPEC)
    result = synthesize(spec)
    assert result.winner is not None
    feasible = [item for item in result.candidates if item.feasible and item.id != result.winner.id]
    assert feasible

    winner_hash = configuration_ir_hash(lower_configuration_ir(spec, result.winner))
    alternate_hash = configuration_ir_hash(lower_configuration_ir(spec, feasible[0]))
    assert winner_hash != alternate_hash

    changed_spec = parse_workload_text(SPEC.replace("record_count: 10000", "record_count: 11000"))
    changed_result = synthesize(changed_spec)
    assert changed_result.winner is not None
    changed_hash = configuration_ir_hash(lower_configuration_ir(changed_spec, changed_result.winner))
    assert changed_hash != winner_hash
