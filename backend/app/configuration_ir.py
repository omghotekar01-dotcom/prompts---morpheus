from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .models import Assignment, CandidateResult, QueryKind, WorkloadSpec
from .primitive_manifest import PRIMITIVE_MANIFEST_VERSION, primitive_manifest_hash
from .workload_ir import WORKLOAD_IR_VERSION, lower_and_hash_workload_ir


CONFIGURATION_IR_VERSION = "morpheus-configuration-ir-v1"
_MUTATION_KINDS = {QueryKind.INSERT, QueryKind.UPDATE, QueryKind.DELETE}


class ConfigurationRouteIR(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    query_index: int = Field(ge=0)
    query_kind: QueryKind
    field: str | None = None
    primitive: str
    materializes_structure: bool
    structure_id: str | None = None
    physical_key_policy: str
    mutation_policy: str | None = None


class ConfigurationCostIR(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    predicted_latency_us: float = Field(ge=0)
    predicted_memory_mb: float = Field(ge=0)
    predicted_build_ms: float = Field(ge=0)
    predicted_update_us: float = Field(ge=0)
    scalar_score: float
    prediction_source: str
    uncertainty_ratio: float = Field(ge=0)
    evidence_state: str = "PREDICTED_CONFIGURATION_COST_VECTOR"


class ConfigurationIR(BaseModel):
    """Canonical physical-design contract selected by MORPHEUS.

    CandidateResult is a search/reporting object. ConfigurationIR is the stable
    compiler/code-generation identity: it binds the candidate to the canonical
    workload semantics and primitive catalog, spells out one physical structure
    per generated route, records duplicate/mutation policy, and carries the
    exact predicted cost vector used for the decision.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    ir_version: str = CONFIGURATION_IR_VERSION
    workload_ir_version: str = WORKLOAD_IR_VERSION
    workload_ir_hash: str
    primitive_manifest_version: str = PRIMITIVE_MANIFEST_VERSION
    primitive_manifest_hash: str
    candidate_id: str
    feasible: bool
    rejection_reasons: tuple[str, ...]
    routes: tuple[ConfigurationRouteIR, ...]
    cost: ConfigurationCostIR
    ownership_policy: str = "generated_record_store_owns_logical_records_and_secondary_indexes_reference_stable_slots"
    mutation_policy: str = "record_mutations_update_every_materialized_secondary_index_before_return"


def _physical_policy(assignment: Assignment) -> tuple[bool, str, str | None]:
    if assignment.query_kind in _MUTATION_KINDS:
        return False, "no_independent_physical_key", "maintain_all_materialized_query_indexes"
    if assignment.query_kind == QueryKind.GRAPH_TRAVERSAL:
        return True, "external_topology_node_id", None
    if assignment.primitive == "bitmap":
        return True, "logical_value_to_all_stable_slot_postings", None
    if assignment.primitive == "radix_trie":
        return True, "string_key_to_duplicate_preserving_stable_slot_postings", None
    if assignment.query_kind == QueryKind.RANGE_SCAN:
        return True, "logical_key_stable_slot_pair", None
    return True, "logical_key_to_last_live_stable_slot_winner", None


def lower_configuration_ir(spec: WorkloadSpec, candidate: CandidateResult) -> ConfigurationIR:
    workload_ir, workload_digest = lower_and_hash_workload_ir(spec)
    routes: list[ConfigurationRouteIR] = []
    for assignment in sorted(candidate.assignments, key=lambda item: item.query_index):
        materializes, policy, mutation_policy = _physical_policy(assignment)
        structure_id = (
            f"s{assignment.query_index}:{assignment.primitive}:{assignment.field or 'global'}"
            if materializes
            else None
        )
        routes.append(
            ConfigurationRouteIR(
                query_index=assignment.query_index,
                query_kind=assignment.query_kind,
                field=assignment.field,
                primitive=assignment.primitive,
                materializes_structure=materializes,
                structure_id=structure_id,
                physical_key_policy=policy,
                mutation_policy=mutation_policy,
            )
        )

    return ConfigurationIR(
        workload_ir_version=workload_ir.ir_version,
        workload_ir_hash=workload_digest,
        primitive_manifest_hash=primitive_manifest_hash(),
        candidate_id=candidate.id,
        feasible=candidate.feasible,
        rejection_reasons=tuple(candidate.rejection_reasons),
        routes=tuple(routes),
        cost=ConfigurationCostIR(
            predicted_latency_us=candidate.predicted_latency_us,
            predicted_memory_mb=candidate.predicted_memory_mb,
            predicted_build_ms=candidate.predicted_build_ms,
            predicted_update_us=candidate.predicted_update_us,
            scalar_score=candidate.score,
            prediction_source=candidate.prediction_source,
            uncertainty_ratio=candidate.uncertainty_ratio,
        ),
    )


def canonical_configuration_ir_dict(ir: ConfigurationIR) -> dict[str, Any]:
    return ir.model_dump(mode="json", exclude_none=True)


def canonical_configuration_ir_json(ir: ConfigurationIR) -> str:
    return json.dumps(
        canonical_configuration_ir_dict(ir),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def configuration_ir_hash(ir: ConfigurationIR) -> str:
    return hashlib.sha256(canonical_configuration_ir_json(ir).encode("utf-8")).hexdigest()


def lower_and_hash_configuration_ir(
    spec: WorkloadSpec,
    candidate: CandidateResult,
) -> tuple[ConfigurationIR, str]:
    ir = lower_configuration_ir(spec, candidate)
    return ir, configuration_ir_hash(ir)
