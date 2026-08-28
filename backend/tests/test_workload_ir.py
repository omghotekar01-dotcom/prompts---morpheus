from __future__ import annotations

import json
import textwrap

import pytest
from pydantic import ValidationError

from app.parser import parse_workload_text, semantic_hash
from app.workload_ir import (
    WORKLOAD_IR_VERSION,
    canonical_ir_json,
    lower_workload_ir,
    workload_ir_hash,
)


RAW = textwrap.dedent(
    """
    version: mws-0.1
    name: ir_demo
    record_count: 10000
    fields:
      - name: id
        type: uint64
        cardinality: 10000
      - name: score
        type: double
      - name: name
        type: string
        cardinality: 5000
    queries:
      - kind: point_lookup
        field: id
        weight: 6
      - kind: range_scan
        field: score
        weight: 3
      - kind: prefix_search
        field: name
        weight: 1
        prefix_length: 3
    constraints:
      memory_mb: 128
      update_rate: 50
    """
).strip()


def test_lowering_is_deterministic_typed_and_hash_stable() -> None:
    first_spec = parse_workload_text(RAW)
    second_spec = parse_workload_text(json.dumps(first_spec.model_dump(mode="json", exclude_none=True)))

    first = lower_workload_ir(first_spec)
    second = lower_workload_ir(second_spec)

    assert first.ir_version == WORKLOAD_IR_VERSION
    assert first.source_spec_hash == semantic_hash(first_spec)
    assert first.fields[0].id == "f0:id"
    assert first.fields[0].type_family == "integer"
    assert first.fields[1].type_family == "floating"
    assert first.fields[2].type_family == "string"
    assert [item.id for item in first.operations] == [
        "q0:point_lookup",
        "q1:range_scan",
        "q2:prefix_search",
    ]
    assert [item.normalized_weight for item in first.operations] == pytest.approx([0.6, 0.3, 0.1])
    assert first.operations[1].required_access_pattern == "ordered_interval_scan"
    assert first.operations[1].selectivity == pytest.approx(0.05)
    assert any("selectivity resolved to default 0.05" in item for item in first.assumptions)

    # Canonical IR identity is independent of YAML vs equivalent JSON syntax.
    assert canonical_ir_json(first) == canonical_ir_json(second)
    assert workload_ir_hash(first) == workload_ir_hash(second)


def test_lowered_ir_is_immutable() -> None:
    ir = lower_workload_ir(parse_workload_text(RAW))
    with pytest.raises(ValidationError):
        ir.name = "mutated"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        ir.fields[0].name = "mutated"  # type: ignore[misc]


def test_ir_hash_changes_when_resolved_semantics_change() -> None:
    original = lower_workload_ir(parse_workload_text(RAW))
    changed = lower_workload_ir(parse_workload_text(RAW.replace("weight: 6", "weight: 5")))
    assert workload_ir_hash(original) != workload_ir_hash(changed)
