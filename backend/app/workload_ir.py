from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .models import QueryKind, WorkloadSpec
from .parser import semantic_hash


WORKLOAD_IR_VERSION = "morpheus-workload-ir-v1"


class IRField(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    ordinal: int = Field(ge=0)
    name: str
    source_type: str
    type_family: Literal["integer", "floating", "string", "boolean", "opaque"]
    cardinality: int | None = Field(default=None, ge=1)


class IROperation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    ordinal: int = Field(ge=0)
    kind: QueryKind
    field_id: str | None = None
    field_name: str | None = None
    normalized_weight: float = Field(gt=0, le=1)
    selectivity: float | None = Field(default=None, gt=0, le=1)
    result_limit: int | None = Field(default=None, ge=1)
    prefix_length: int | None = Field(default=None, ge=1)
    mutating: bool
    required_access_pattern: str


class IRConstraints(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    memory_mb: float | None = Field(default=None, gt=0)
    p99_latency_us: float | None = Field(default=None, gt=0)
    update_rate: float = Field(ge=0)
    build_time_ms: float | None = Field(default=None, gt=0)


class IRObjective(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    latency: float = Field(ge=0)
    memory: float = Field(ge=0)
    update: float = Field(ge=0)
    build: float = Field(ge=0)


class WorkloadIR(BaseModel):
    """Canonical immutable compiler IR lowered from a validated MWS document.

    The IR deliberately contains only resolved semantic information needed by
    synthesis. Presentation syntax, YAML ordering and comments cannot affect its
    identity. Operation weights are normalized, field/operation IDs are stable,
    defaults already resolved by WorkloadSpec are explicit, and the source MWS
    hash is retained as provenance.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    ir_version: str = WORKLOAD_IR_VERSION
    source_spec_version: str
    source_spec_hash: str
    name: str
    record_count: int = Field(ge=1)
    fields: tuple[IRField, ...]
    operations: tuple[IROperation, ...]
    constraints: IRConstraints
    objective: IRObjective
    assumptions: tuple[str, ...] = ()


def _type_family(raw: str) -> Literal["integer", "floating", "string", "boolean", "opaque"]:
    lowered = raw.lower()
    if lowered in {"uint64", "uint64_t", "uint32", "uint32_t", "int", "integer"}:
        return "integer"
    if lowered in {"float", "double"}:
        return "floating"
    if lowered in {"string", "str", "text", "char"}:
        return "string"
    if lowered in {"bool", "boolean"}:
        return "boolean"
    return "opaque"


def _access_pattern(kind: QueryKind) -> str:
    return {
        QueryKind.POINT_LOOKUP: "exact_key_lookup",
        QueryKind.RANGE_SCAN: "ordered_interval_scan",
        QueryKind.FILTER: "equality_filter_postings",
        QueryKind.PREFIX_SEARCH: "ordered_string_prefix",
        QueryKind.GRAPH_TRAVERSAL: "graph_adjacency_traversal",
        QueryKind.INSERT: "record_insert_maintenance",
        QueryKind.UPDATE: "record_update_maintenance",
        QueryKind.DELETE: "record_delete_maintenance",
    }[kind]


def lower_workload_ir(spec: WorkloadSpec) -> WorkloadIR:
    """Deterministically lower resolved MWS into canonical typed WorkloadIR."""

    field_ids = {field.name: f"f{index}:{field.name}" for index, field in enumerate(spec.fields)}
    fields = tuple(
        IRField(
            id=field_ids[field.name],
            ordinal=index,
            name=field.name,
            source_type=field.type,
            type_family=_type_family(field.type),
            cardinality=field.cardinality,
        )
        for index, field in enumerate(spec.fields)
    )

    total_weight = sum(query.weight for query in spec.queries)
    if total_weight <= 0:  # guarded by WorkloadSpec, retained as compiler invariant
        raise ValueError("resolved workload operation weights must have positive total")

    mutation_kinds = {QueryKind.INSERT, QueryKind.UPDATE, QueryKind.DELETE}
    operations = tuple(
        IROperation(
            id=f"q{index}:{query.kind.value}",
            ordinal=index,
            kind=query.kind,
            field_id=field_ids.get(query.field) if query.field else None,
            field_name=query.field,
            normalized_weight=query.weight / total_weight,
            selectivity=query.selectivity,
            result_limit=query.result_limit,
            prefix_length=query.prefix_length,
            mutating=query.kind in mutation_kinds,
            required_access_pattern=_access_pattern(query.kind),
        )
        for index, query in enumerate(spec.queries)
    )

    assumptions: list[str] = []
    for index, query in enumerate(spec.queries):
        if query.kind in {QueryKind.RANGE_SCAN, QueryKind.FILTER} and "selectivity" not in query.model_fields_set:
            assumptions.append(
                f"q{index}:{query.kind.value}.selectivity resolved to default {query.selectivity}"
            )
    if "constraints" not in spec.model_fields_set:
        assumptions.append("constraints resolved from MWS defaults")
    if "objective" not in spec.model_fields_set:
        assumptions.append("objective weights resolved from MWS defaults")

    return WorkloadIR(
        source_spec_version=spec.version,
        source_spec_hash=semantic_hash(spec),
        name=spec.name,
        record_count=spec.record_count,
        fields=fields,
        operations=operations,
        constraints=IRConstraints(**spec.constraints.model_dump()),
        objective=IRObjective(**spec.objective.model_dump()),
        assumptions=tuple(assumptions),
    )


def canonical_ir_dict(ir: WorkloadIR) -> dict[str, Any]:
    return ir.model_dump(mode="json", exclude_none=True)


def canonical_ir_json(ir: WorkloadIR) -> str:
    return json.dumps(canonical_ir_dict(ir), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def workload_ir_hash(ir: WorkloadIR) -> str:
    return hashlib.sha256(canonical_ir_json(ir).encode("utf-8")).hexdigest()


def lower_and_hash_workload_ir(spec: WorkloadSpec) -> tuple[WorkloadIR, str]:
    ir = lower_workload_ir(spec)
    return ir, workload_ir_hash(ir)
