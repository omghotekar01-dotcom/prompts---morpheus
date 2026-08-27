from __future__ import annotations

import hashlib
import itertools
import math
from collections import defaultdict

from .catalog import PRIMITIVES, compatible_primitives
from .codegen import generate_cpp_preview
from .models import Assignment, CandidateResult, QueryKind, QuerySpec, SynthesisResult, WorkloadSpec
from .parser import semantic_hash


MAX_ENUMERATED_CONFIGS = 512


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
        # Bitmap can still work without a known cardinality; avoid it for explicitly very high-cardinality columns.
        if field.cardinality and field.cardinality > max(100_000, spec.record_count // 3):
            return False
    return True


def _candidate_options(spec: WorkloadSpec, query: QuerySpec) -> list[str]:
    items = [p.name for p in compatible_primitives(query.kind) if _primitive_compatible_with_query(spec, query, p.name)]
    # Stable order is a reproducibility requirement.
    return sorted(items)


def _latency_for(spec: WorkloadSpec, query: QuerySpec, primitive_name: str) -> float:
    primitive = PRIMITIVES[primitive_name]
    base = primitive.base_latency_us[query.kind]
    n = max(spec.record_count, 2)
    log_factor = max(math.log2(n) / 20.0, 0.25)
    selectivity = query.selectivity if query.selectivity is not None else 0.01

    if primitive_name == "robin_hood_hash":
        return base * (1.0 + 0.02 * log_factor)
    if primitive_name == "ordered_tree":
        if query.kind == QueryKind.RANGE_SCAN:
            return base * log_factor + (selectivity * n) * 0.00004
        return base * log_factor
    if primitive_name == "sorted_array":
        if query.kind == QueryKind.RANGE_SCAN:
            return base * log_factor + (selectivity * n) * 0.000025
        return base * log_factor
    if primitive_name == "radix_trie":
        prefix_factor = max((query.prefix_length or 4) / 4.0, 0.5)
        return base * prefix_factor
    if primitive_name == "bitmap":
        return base + (selectivity * n) * 0.000012
    if primitive_name == "csr_graph":
        return base * max(math.sqrt(n) / 300.0, 1.0)
    return base


def _evaluate_configuration(spec: WorkloadSpec, primitive_names: tuple[str, ...]) -> CandidateResult:
    assignments: list[Assignment] = []
    weighted_latency = 0.0
    total_weight = 0.0

    for idx, (query, primitive_name) in enumerate(zip(spec.queries, primitive_names, strict=True)):
        assignments.append(
            Assignment(
                query_index=idx,
                query_kind=query.kind,
                field=query.field,
                primitive=primitive_name,
            )
        )
        latency = _latency_for(spec, query, primitive_name)
        weighted_latency += latency * query.weight
        total_weight += query.weight

    predicted_latency = weighted_latency / max(total_weight, 1e-12)
    unique = sorted(set(primitive_names))
    memory_bytes = sum(PRIMITIVES[name].memory_bytes_per_record * spec.record_count for name in unique)
    predicted_memory_mb = memory_bytes / (1024 * 1024)
    build_ns = sum(PRIMITIVES[name].build_ns_per_record * spec.record_count for name in unique)
    predicted_build_ms = build_ns / 1_000_000

    update_primitives = [PRIMITIVES[name].update_latency_us for name in unique]
    predicted_update_us = sum(update_primitives) / len(update_primitives) if update_primitives else 0.0

    rejections: list[str] = []
    constraints = spec.constraints
    if constraints.memory_mb is not None and predicted_memory_mb > constraints.memory_mb:
        rejections.append(
            f"predicted memory {predicted_memory_mb:.2f} MB exceeds hard limit {constraints.memory_mb:.2f} MB"
        )
    if constraints.p99_latency_us is not None and predicted_latency > constraints.p99_latency_us:
        rejections.append(
            f"predicted aggregate latency {predicted_latency:.3f} us exceeds hard p99 proxy {constraints.p99_latency_us:.3f} us"
        )
    if constraints.build_time_ms is not None and predicted_build_ms > constraints.build_time_ms:
        rejections.append(
            f"predicted build {predicted_build_ms:.2f} ms exceeds hard limit {constraints.build_time_ms:.2f} ms"
        )

    # Bootstrap objective normalization: explicit, deterministic and intentionally simple until calibration exists.
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
    )


def synthesize(spec: WorkloadSpec) -> SynthesisResult:
    options = [_candidate_options(spec, query) for query in spec.queries]
    unsupported = [idx for idx, candidates in enumerate(options) if not candidates]
    if unsupported:
        return SynthesisResult(
            spec_hash=semantic_hash(spec),
            winner=None,
            candidates=[],
            warnings=[f"no compatible primitive exists for query indexes: {unsupported}"],
            explanation=["Synthesis stopped before ranking because capability compatibility is a hard gate."],
        )

    # Enumerate a bounded deterministic prefix of the Cartesian product. Search improvements arrive in P6.
    product = itertools.product(*options)
    candidates = [_evaluate_configuration(spec, combo) for combo in itertools.islice(product, MAX_ENUMERATED_CONFIGS)]
    candidates.sort(key=lambda c: (not c.feasible, c.score, c.predicted_memory_mb, c.id))

    feasible = [candidate for candidate in candidates if candidate.feasible]
    winner = feasible[0] if feasible else None

    explanation: list[str] = []
    warnings = [
        "Cost values are bootstrap predictions from deterministic priors; they are not benchmark measurements.",
        "P5 calibration will replace bootstrap priors with target-machine observations and uncertainty estimates.",
    ]

    if winner:
        query_groups: dict[str, list[str]] = defaultdict(list)
        for assignment in winner.assignments:
            label = f"{assignment.query_kind.value}" + (f"({assignment.field})" if assignment.field else "")
            query_groups[assignment.primitive].append(label)
        for primitive_name in winner.unique_primitives:
            display = PRIMITIVES[primitive_name].display_name
            explanation.append(f"{display} serves: {', '.join(query_groups[primitive_name])}.")
        explanation.append(
            f"Winner {winner.id} is the lowest-score feasible configuration among {len(candidates)} evaluated candidates."
        )
        generated = generate_cpp_preview(spec, winner)
    else:
        generated = None
        explanation.append("No candidate satisfies all hard constraints; constraints were not relaxed.")

    theoretical_count = math.prod(len(item) for item in options)
    if theoretical_count > MAX_ENUMERATED_CONFIGS:
        warnings.append(
            f"Candidate space has {theoretical_count} configurations; MVP evaluated deterministic first {MAX_ENUMERATED_CONFIGS}."
        )

    return SynthesisResult(
        spec_hash=semantic_hash(spec),
        winner=winner,
        candidates=candidates,
        generated_code=generated,
        explanation=explanation,
        warnings=warnings,
    )
