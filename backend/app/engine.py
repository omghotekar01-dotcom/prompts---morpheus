from __future__ import annotations

import hashlib
import itertools
import math
from collections import defaultdict
from typing import Iterable

from .calibration import CALIBRATIONS
from .catalog import PRIMITIVES, compatible_primitives
from .codegen import generate_cpp_preview
from .cost_model import estimate_build_ms, estimate_query_latency_us, estimate_update_us
from .models import (
    Assignment,
    CandidateResult,
    QueryKind,
    QuerySpec,
    SearchStrategy,
    SearchSummary,
    SynthesisResult,
    WorkloadSpec,
)
from .parser import semantic_hash
from .workload_ir import WORKLOAD_IR_VERSION, lower_and_hash_workload_ir


DEFAULT_MAX_CANDIDATES = 4096
DEFAULT_BEAM_WIDTH = 128
MAX_PARETO_RESULTS = 64
_MUTATION_KINDS = {QueryKind.INSERT, QueryKind.UPDATE, QueryKind.DELETE}


def _field_type(spec: WorkloadSpec, field: str | None) -> str | None:
    if field is None:
        return None
    for item in spec.fields:
        if item.name == field:
            return item.type.lower()
    return None


def _primitive_compatible_with_query(spec: WorkloadSpec, query: QuerySpec, primitive_name: str) -> bool:
    primitive = PRIMITIVES[primitive_name]
    if query.kind not in primitive.capabilities:
        return False

    field_type = _field_type(spec, query.field)
    if primitive_name == "radix_trie" and field_type is not None:
        return any(token in field_type for token in ("str", "string", "text", "char"))
    if primitive_name == "bitmap" and query.field:
        field = next(item for item in spec.fields if item.name == query.field)
        if field.cardinality and field.cardinality > max(100_000, spec.record_count // 3):
            return False
    return True


def _candidate_options(spec: WorkloadSpec, query: QuerySpec) -> list[str]:
    items = [p.name for p in compatible_primitives(query.kind) if _primitive_compatible_with_query(spec, query, p.name)]
    return sorted(items)


def _prediction_source(sources: Iterable[str]) -> str:
    source_list = list(sources)
    calibrated = [item for item in source_list if item.startswith("CALIBRATED:")]
    if not calibrated:
        return "BOOTSTRAP_PRIOR"
    if len(calibrated) == len(source_list):
        profile_ids = sorted({item.split(":", 1)[1] for item in calibrated})
        return f"CALIBRATED_ANCHORED_MODEL:{','.join(profile_ids)}"
    profile_ids = sorted({item.split(":", 1)[1] for item in calibrated})
    return f"MIXED_CALIBRATED_BOOTSTRAP:{','.join(profile_ids)}"


def _physical_assignments(assignments: Iterable[Assignment]) -> list[Assignment]:
    """Return assignments that materialize physical generated members.

    Current artifact code generation emits one physical member per non-mutation
    query route. It deliberately does not emit a separate index for INSERT,
    UPDATE or DELETE declarations; mutations maintain every materialized read
    structure. Cost accounting must mirror that implementation rather than
    deduplicating by primitive family, otherwise two indexes of the same family
    on different routes are incorrectly charged only once.
    """

    return [item for item in assignments if item.query_kind not in _MUTATION_KINDS]


def _physical_memory_bytes(spec: WorkloadSpec, assignments: Iterable[Assignment]) -> float:
    return sum(
        PRIMITIVES[item.primitive].memory_bytes_per_record * spec.record_count
        for item in _physical_assignments(assignments)
    )


def _evaluate_configuration(spec: WorkloadSpec, primitive_names: tuple[str, ...]) -> CandidateResult:
    assignments: list[Assignment] = []
    weighted_latency = 0.0
    total_weight = 0.0
    estimate_sources: list[str] = []
    uncertainties: list[float] = []
    profile = CALIBRATIONS.active()

    for idx, (query, primitive_name) in enumerate(zip(spec.queries, primitive_names, strict=True)):
        assignments.append(
            Assignment(
                query_index=idx,
                query_kind=query.kind,
                field=query.field,
                primitive=primitive_name,
            )
        )
        estimate = estimate_query_latency_us(spec, query, primitive_name, profile=profile)
        weighted_latency += estimate.value * query.weight
        total_weight += query.weight
        estimate_sources.append(estimate.source)
        uncertainties.append(estimate.uncertainty_ratio)

    predicted_latency = weighted_latency / max(total_weight, 1e-12)
    unique = sorted(set(primitive_names))
    physical = _physical_assignments(assignments)

    # Match generated architecture: every non-mutation query route owns its own
    # physical member even when several routes use the same primitive family.
    # This is index-memory only; record payload, allocator slack and process RSS
    # remain outside the bootstrap model and are called out in result warnings.
    memory_bytes = _physical_memory_bytes(spec, physical)
    predicted_memory_mb = memory_bytes / (1024 * 1024)

    build_estimates = [estimate_build_ms(spec, item.primitive, profile=profile) for item in physical]
    predicted_build_ms = sum(item.value for item in build_estimates)
    estimate_sources.extend(item.source for item in build_estimates)
    uncertainties.extend(item.uncertainty_ratio for item in build_estimates)

    # One record mutation must maintain every materialized generated index. Sum
    # maintenance estimates rather than averaging distinct primitive families.
    update_estimates = [estimate_update_us(item.primitive, profile=profile) for item in physical]
    predicted_update_us = sum(item.value for item in update_estimates)
    estimate_sources.extend(item.source for item in update_estimates)
    uncertainties.extend(item.uncertainty_ratio for item in update_estimates)

    rejections: list[str] = []
    constraints = spec.constraints
    if constraints.memory_mb is not None and predicted_memory_mb > constraints.memory_mb:
        rejections.append(
            f"predicted index memory {predicted_memory_mb:.2f} MB exceeds hard limit {constraints.memory_mb:.2f} MB"
        )
    if constraints.p99_latency_us is not None and predicted_latency > constraints.p99_latency_us:
        rejections.append(
            f"predicted aggregate latency {predicted_latency:.3f} us exceeds hard p99 proxy {constraints.p99_latency_us:.3f} us"
        )
    if constraints.build_time_ms is not None and predicted_build_ms > constraints.build_time_ms:
        rejections.append(
            f"predicted build {predicted_build_ms:.2f} ms exceeds hard limit {constraints.build_time_ms:.2f} ms"
        )

    objective = spec.objective
    memory_reference = constraints.memory_mb or max(predicted_memory_mb, 1.0)
    build_reference = constraints.build_time_ms or max(predicted_build_ms, 1.0)
    update_pressure = math.log10(1.0 + constraints.update_rate)

    score = (
        objective.latency * predicted_latency
        + objective.memory * (predicted_memory_mb / memory_reference)
        + objective.update * predicted_update_us * update_pressure
        + objective.build * (predicted_build_ms / build_reference)
    )

    identity = "|".join(f"{a.query_index}:{a.primitive}" for a in assignments)
    candidate_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]

    return CandidateResult(
        id=candidate_id,
        assignments=assignments,
        unique_primitives=unique,
        predicted_latency_us=round(predicted_latency, 6),
        predicted_memory_mb=round(predicted_memory_mb, 6),
        predicted_build_ms=round(predicted_build_ms, 6),
        predicted_update_us=round(predicted_update_us, 6),
        score=round(score, 9),
        feasible=not rejections,
        rejection_reasons=rejections,
        prediction_source=_prediction_source(estimate_sources),
        uncertainty_ratio=round(max(uncertainties, default=0.50), 4),
    )


def _partial_priority(spec: WorkloadSpec, prefix: tuple[str, ...]) -> tuple[float, float, tuple[str, ...]]:
    """Deterministic beam-search priority for a partial configuration.

    It favors low weighted latency while charging each query route that has
    already materialized a physical member. It is a heuristic only; finalists
    are always re-evaluated using the complete objective and hard constraints.
    """

    weighted_latency = 0.0
    weight = 0.0
    profile = CALIBRATIONS.active()
    partial_assignments: list[Assignment] = []
    for index, (query, primitive_name) in enumerate(zip(spec.queries, prefix, strict=False)):
        estimate = estimate_query_latency_us(spec, query, primitive_name, profile=profile)
        weighted_latency += estimate.value * query.weight
        weight += query.weight
        partial_assignments.append(
            Assignment(
                query_index=index,
                query_kind=query.kind,
                field=query.field,
                primitive=primitive_name,
            )
        )
    latency = weighted_latency / max(weight, 1e-12)
    memory_mb = _physical_memory_bytes(spec, partial_assignments) / (1024 * 1024)

    if spec.constraints.memory_mb is not None and memory_mb > spec.constraints.memory_mb:
        # Retain deterministic ordering but send hard-infeasible prefixes to the back.
        latency += 1_000_000.0
    return (latency, memory_mb, prefix)


def _beam_combinations(spec: WorkloadSpec, options: list[list[str]], beam_width: int) -> list[tuple[str, ...]]:
    beam: list[tuple[str, ...]] = [tuple()]
    for candidates in options:
        expanded = [prefix + (choice,) for prefix in beam for choice in candidates]
        expanded.sort(key=lambda prefix: _partial_priority(spec, prefix))
        beam = expanded[:beam_width]
    return beam


def _pareto_front(candidates: list[CandidateResult]) -> list[CandidateResult]:
    feasible = [candidate for candidate in candidates if candidate.feasible]
    front: list[CandidateResult] = []
    for candidate in feasible:
        vector = (
            candidate.predicted_latency_us,
            candidate.predicted_memory_mb,
            candidate.predicted_update_us,
            candidate.predicted_build_ms,
        )
        dominated = False
        for other in feasible:
            if other.id == candidate.id:
                continue
            other_vector = (
                other.predicted_latency_us,
                other.predicted_memory_mb,
                other.predicted_update_us,
                other.predicted_build_ms,
            )
            no_worse = all(a <= b for a, b in zip(other_vector, vector, strict=True))
            strictly_better = any(a < b for a, b in zip(other_vector, vector, strict=True))
            if no_worse and strictly_better:
                dominated = True
                break
        if not dominated:
            front.append(candidate)
    front.sort(key=lambda c: (c.score, c.predicted_latency_us, c.predicted_memory_mb, c.id))
    return front[:MAX_PARETO_RESULTS]


def synthesize(
    spec: WorkloadSpec,
    *,
    strategy: SearchStrategy = SearchStrategy.AUTO,
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
    beam_width: int = DEFAULT_BEAM_WIDTH,
) -> SynthesisResult:
    if max_candidates < 1:
        raise ValueError("max_candidates must be positive")
    if beam_width < 1:
        raise ValueError("beam_width must be positive")

    workload_ir, workload_ir_digest = lower_and_hash_workload_ir(spec)
    options = [_candidate_options(spec, query) for query in spec.queries]
    unsupported = [idx for idx, candidates in enumerate(options) if not candidates]
    theoretical_count = math.prod(len(item) for item in options) if options else 0

    if unsupported:
        return SynthesisResult(
            spec_hash=semantic_hash(spec),
            workload_ir_hash=workload_ir_digest,
            workload_ir_version=workload_ir.ir_version,
            winner=None,
            candidates=[],
            warnings=[f"no compatible primitive exists for query indexes: {unsupported}"],
            explanation=["Synthesis stopped before ranking because capability compatibility is a hard gate."],
            search_summary=SearchSummary(
                strategy=strategy,
                theoretical_configurations=theoretical_count,
                evaluated_configurations=0,
                feasible_configurations=0,
                truncated=False,
                max_candidates=max_candidates,
                beam_width=beam_width if strategy == SearchStrategy.BEAM else None,
            ),
            active_calibration_profile=CALIBRATIONS.active_profile_id,
        )

    selected_strategy = strategy
    if strategy == SearchStrategy.AUTO:
        selected_strategy = (
            SearchStrategy.EXHAUSTIVE if theoretical_count <= max_candidates else SearchStrategy.BEAM
        )

    if selected_strategy == SearchStrategy.BEAM:
        combinations = _beam_combinations(spec, options, min(beam_width, max_candidates))
        truncated = theoretical_count > len(combinations)
    else:
        combinations = list(itertools.islice(itertools.product(*options), max_candidates))
        truncated = theoretical_count > len(combinations)

    candidates = [_evaluate_configuration(spec, combo) for combo in combinations]
    candidates.sort(key=lambda c: (not c.feasible, c.score, c.predicted_memory_mb, c.id))
    feasible = [candidate for candidate in candidates if candidate.feasible]
    winner = feasible[0] if feasible else None
    pareto = _pareto_front(candidates)

    explanation: list[str] = []
    warnings: list[str] = []
    active_profile = CALIBRATIONS.active()
    if active_profile is None:
        evidence_state = "PREDICTED_NOT_MEASURED"
        warnings.extend(
            [
                "Cost values are bootstrap predictions from deterministic priors; they are not benchmark measurements.",
                "Import and activate a calibration profile to anchor supported operations to target-machine measurements.",
            ]
        )
    else:
        evidence_state = "CALIBRATED_MODEL_NOT_END_TO_END_MEASURED"
        warnings.extend(
            [
                f"Active calibration profile {active_profile.id} anchors only operations present in its measurement artifact.",
                "Candidate-level performance remains a model prediction until the generated configuration is benchmarked end-to-end.",
            ]
        )

    warnings.append(
        "Predicted memory currently models generated index members per query route; record payload, allocator slack, caches, code, and process RSS require end-to-end measurement."
    )
    if any(query.kind in _MUTATION_KINDS for query in spec.queries):
        warnings.append(
            "Mutation declarations are cost-model workload signals, not standalone generated indexes; generated record mutations maintain all materialized query indexes."
        )

    if winner:
        query_groups: dict[str, list[str]] = defaultdict(list)
        for assignment in winner.assignments:
            label = f"{assignment.query_kind.value}" + (f"({assignment.field})" if assignment.field else "")
            query_groups[assignment.primitive].append(label)
        for primitive_name in winner.unique_primitives:
            display = PRIMITIVES[primitive_name].display_name
            explanation.append(f"{display} serves: {', '.join(query_groups[primitive_name])}.")
        explanation.append(
            f"Winner {winner.id} is the lowest-score feasible finalist among {len(candidates)} evaluated configurations."
        )
        explanation.append(
            f"Search used {selected_strategy.value}; Pareto analysis retained {len(pareto)} non-dominated feasible configurations."
        )
        explanation.append(
            f"Decision input is canonical {WORKLOAD_IR_VERSION} {workload_ir_digest[:16]}… derived from source MWS {workload_ir.source_spec_hash[:16]}…."
        )
        generated = generate_cpp_preview(spec, winner)
    else:
        generated = None
        explanation.append("No evaluated candidate satisfies all hard constraints; constraints were not relaxed.")

    if truncated:
        if selected_strategy == SearchStrategy.BEAM:
            warnings.append(
                f"Configuration space has {theoretical_count} combinations; deterministic beam search retained {len(combinations)} finalists."
            )
        else:
            warnings.append(
                f"Explicit exhaustive search budget stopped after {len(combinations)} of {theoretical_count} configurations."
            )
    if spec.constraints.p99_latency_us is not None:
        warnings.append(
            "The current p99 constraint is checked against the aggregate latency model proxy; true p99 requires benchmark distributions."
        )

    return SynthesisResult(
        spec_hash=semantic_hash(spec),
        workload_ir_hash=workload_ir_digest,
        workload_ir_version=workload_ir.ir_version,
        evidence_state=evidence_state,
        winner=winner,
        candidates=candidates,
        generated_code=generated,
        explanation=explanation,
        warnings=warnings,
        search_summary=SearchSummary(
            strategy=selected_strategy,
            theoretical_configurations=theoretical_count,
            evaluated_configurations=len(candidates),
            feasible_configurations=len(feasible),
            truncated=truncated,
            max_candidates=max_candidates,
            beam_width=beam_width if selected_strategy == SearchStrategy.BEAM else None,
        ),
        pareto_front=pareto,
        active_calibration_profile=CALIBRATIONS.active_profile_id,
    )