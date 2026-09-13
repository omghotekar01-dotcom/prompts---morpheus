from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import dataclass
from typing import Any

from .catalog import PRIMITIVES
from .engine import synthesize
from .models import AccessDistribution, CandidateResult, QueryKind, SearchStrategy, WorkloadSpec
from .parser import parse_workload_text, semantic_hash


FUZZ_SCHEMA = "morpheus-property-fuzz-v1"
FUZZ_EVIDENCE_STATE = "DETERMINISTIC_PROPERTY_FUZZ_NOT_BENCHMARK"
DEFAULT_CASES = 32
DEFAULT_SEED = 20260913


@dataclass(frozen=True)
class FuzzFailure:
    case_index: int
    case_seed: int
    invariant: str
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_index": self.case_index,
            "case_seed": self.case_seed,
            "invariant": self.invariant,
            "detail": self.detail,
        }


def _distribution(rng: random.Random) -> dict[str, Any]:
    kind = rng.choice(list(AccessDistribution))
    if kind == AccessDistribution.ZIPF:
        return {"kind": kind.value, "zipf_theta": round(rng.uniform(0.6, 1.8), 3)}
    if kind == AccessDistribution.HOTSPOT:
        fraction = round(rng.uniform(0.05, 0.4), 3)
        probability = round(rng.uniform(max(fraction, 0.55), 0.98), 3)
        return {
            "kind": kind.value,
            "hotspot_fraction": fraction,
            "hotspot_probability": probability,
        }
    return {"kind": kind.value}


def generate_fuzz_workload(case_seed: int) -> WorkloadSpec:
    """Generate one valid, replayable MWS instance from a single integer seed.

    The generator intentionally spans every current query family while keeping
    field/type constraints valid. It produces test inputs only; it does not
    represent observed customer workloads or benchmark evidence.
    """

    rng = random.Random(case_seed)
    record_count = rng.randint(128, 250_000)
    score_cardinality = rng.randint(2, min(record_count, 50_000))
    label_cardinality = rng.randint(2, min(record_count, 20_000))
    fields = [
        {"name": "id", "type": "uint64", "cardinality": record_count},
        {"name": "score", "type": "uint32", "cardinality": score_cardinality},
        {"name": "label", "type": "string", "cardinality": label_cardinality},
    ]

    query_count = rng.randint(2, 7)
    kinds = list(QueryKind)
    selected = [rng.choice(kinds) for _ in range(query_count)]
    # Make the campaign cover the full capability surface deterministically as
    # case seeds vary, without forcing every case to be unrealistically broad.
    selected[0] = kinds[case_seed % len(kinds)]

    queries: list[dict[str, Any]] = []
    for kind in selected:
        query: dict[str, Any] = {
            "kind": kind.value,
            "weight": round(rng.uniform(0.05, 2.0), 6),
            "distribution": _distribution(rng),
        }
        if kind == QueryKind.POINT_LOOKUP:
            query["field"] = rng.choice(["id", "score", "label"])
        elif kind == QueryKind.RANGE_SCAN:
            query["field"] = rng.choice(["id", "score"])
            query["selectivity"] = round(rng.uniform(0.001, 0.75), 6)
        elif kind == QueryKind.FILTER:
            query["field"] = "score"
            query["selectivity"] = round(rng.uniform(0.001, 0.5), 6)
        elif kind == QueryKind.PREFIX_SEARCH:
            query["field"] = "label"
            query["prefix_length"] = rng.randint(1, 12)
        elif kind in {QueryKind.INSERT, QueryKind.UPDATE, QueryKind.DELETE}:
            query["field"] = "id"
        queries.append(query)

    constraints: dict[str, Any] = {
        "update_rate": round(rng.uniform(0.0, 10_000.0), 3),
    }
    if rng.random() < 0.7:
        constraints["memory_mb"] = round(rng.uniform(4.0, 512.0), 3)
    if rng.random() < 0.55:
        constraints["p99_latency_us"] = round(rng.uniform(0.05, 250.0), 4)
    if rng.random() < 0.45:
        constraints["build_time_ms"] = round(rng.uniform(0.05, 5000.0), 4)

    objective_values = [rng.uniform(0.0, 1.5) for _ in range(4)]
    if max(objective_values) == 0:
        objective_values[0] = 1.0
    objective = dict(zip(("latency", "memory", "update", "build"), objective_values, strict=True))

    raw = {
        "version": "mws-0.1",
        "name": f"property_fuzz_{case_seed}",
        "record_count": record_count,
        "fields": fields,
        "queries": queries,
        "constraints": constraints,
        "objective": {key: round(value, 6) for key, value in objective.items()},
    }
    return parse_workload_text(json.dumps(raw, sort_keys=True))


def _dominates(left: CandidateResult, right: CandidateResult) -> bool:
    left_vector = (
        left.predicted_latency_us,
        left.predicted_memory_mb,
        left.predicted_update_us,
        left.predicted_build_ms,
    )
    right_vector = (
        right.predicted_latency_us,
        right.predicted_memory_mb,
        right.predicted_update_us,
        right.predicted_build_ms,
    )
    return all(a <= b for a, b in zip(left_vector, right_vector, strict=True)) and any(
        a < b for a, b in zip(left_vector, right_vector, strict=True)
    )


def _assert_case_invariants(spec: WorkloadSpec, *, max_candidates: int, beam_width: int) -> int:
    checks = 0
    canonical_json = json.dumps(spec.model_dump(mode="json"), sort_keys=True)
    reparsed = parse_workload_text(canonical_json)
    assert semantic_hash(spec) == semantic_hash(reparsed), "semantic hash changed after canonical JSON round-trip"
    checks += 1

    first = synthesize(spec, strategy=SearchStrategy.AUTO, max_candidates=max_candidates, beam_width=beam_width)
    second = synthesize(spec, strategy=SearchStrategy.AUTO, max_candidates=max_candidates, beam_width=beam_width)
    assert first.model_dump(mode="json") == second.model_dump(mode="json"), "synthesis is not deterministic for identical input"
    checks += 1

    summary = first.search_summary
    assert summary is not None, "search summary missing"
    assert summary.evaluated_configurations == len(first.candidates), "evaluated count does not match candidate evidence"
    assert summary.feasible_configurations == sum(candidate.feasible for candidate in first.candidates), "feasible count mismatch"
    checks += 3

    candidate_ids = [candidate.id for candidate in first.candidates]
    assert len(candidate_ids) == len(set(candidate_ids)), "candidate IDs are not unique"
    checks += 1

    for candidate in first.candidates:
        assert candidate.feasible == (not candidate.rejection_reasons), "feasibility disagrees with hard-gate rejection evidence"
        assert all(
            math.isfinite(value) and value >= 0
            for value in (
                candidate.predicted_latency_us,
                candidate.predicted_memory_mb,
                candidate.predicted_build_ms,
                candidate.predicted_update_us,
                candidate.score,
                candidate.uncertainty_ratio,
            )
        ), "candidate contains invalid numeric evidence"
        assert len(candidate.assignments) == len(spec.queries), "candidate does not route every declared operation"
        for assignment in candidate.assignments:
            query = spec.queries[assignment.query_index]
            assert assignment.query_kind == query.kind, "assignment query kind drifted from MWS"
            assert assignment.field == query.field, "assignment field drifted from MWS"
            assert assignment.primitive in PRIMITIVES, "assignment references an unknown primitive"
            assert query.kind in PRIMITIVES[assignment.primitive].capabilities, "assignment violates primitive capability algebra"
        if candidate.feasible:
            constraints = spec.constraints
            if constraints.memory_mb is not None:
                assert candidate.predicted_memory_mb <= constraints.memory_mb, "feasible candidate violates memory hard gate"
            if constraints.p99_latency_us is not None:
                assert candidate.predicted_latency_us <= constraints.p99_latency_us, "feasible candidate violates latency hard gate"
            if constraints.build_time_ms is not None:
                assert candidate.predicted_build_ms <= constraints.build_time_ms, "feasible candidate violates build hard gate"
        checks += 4 + len(candidate.assignments)

    feasible = [candidate for candidate in first.candidates if candidate.feasible]
    if feasible:
        assert first.winner is not None, "feasible search space has no winner"
        assert first.winner.id == feasible[0].id, "winner is not the first ranked feasible candidate"
        assert first.generated_code is not None, "feasible winner did not produce generated C++ preview"
    else:
        assert first.winner is None, "winner exists despite zero feasible candidates"
        assert first.generated_code is None, "generated code exists without a feasible winner"
    checks += 3

    feasible_by_id = {candidate.id: candidate for candidate in feasible}
    pareto_ids = [candidate.id for candidate in first.pareto_front]
    assert len(pareto_ids) == len(set(pareto_ids)), "Pareto front contains duplicates"
    assert set(pareto_ids).issubset(feasible_by_id), "Pareto front contains a rejected candidate"
    for candidate in first.pareto_front:
        assert not any(
            other.id != candidate.id and _dominates(other, candidate)
            for other in feasible
        ), "Pareto front contains a dominated candidate"
    checks += 2 + len(first.pareto_front)

    expected_strategy = SearchStrategy.EXHAUSTIVE if summary.theoretical_configurations <= max_candidates else SearchStrategy.BEAM
    assert summary.strategy == expected_strategy, "AUTO search strategy does not match declared search budget"
    assert summary.evaluated_configurations <= max_candidates, "search evaluated more candidates than declared budget"
    checks += 2
    return checks


def run_property_fuzz_campaign(
    *,
    cases: int = DEFAULT_CASES,
    seed: int = DEFAULT_SEED,
    max_candidates: int = 256,
    beam_width: int = 48,
) -> dict[str, Any]:
    if cases < 1:
        raise ValueError("cases must be positive")
    if max_candidates < 1 or beam_width < 1:
        raise ValueError("search budgets must be positive")

    seed_rng = random.Random(seed)
    failures: list[FuzzFailure] = []
    invariant_checks = 0
    case_seeds: list[int] = []
    for case_index in range(cases):
        case_seed = seed_rng.randrange(0, 2**31)
        case_seeds.append(case_seed)
        try:
            spec = generate_fuzz_workload(case_seed)
            invariant_checks += _assert_case_invariants(
                spec,
                max_candidates=max_candidates,
                beam_width=beam_width,
            )
        except Exception as exc:  # campaign report must preserve replay evidence
            failures.append(
                FuzzFailure(
                    case_index=case_index,
                    case_seed=case_seed,
                    invariant=type(exc).__name__,
                    detail=str(exc),
                )
            )

    return {
        "schema": FUZZ_SCHEMA,
        "evidence_state": FUZZ_EVIDENCE_STATE,
        "campaign_seed": seed,
        "cases_requested": cases,
        "cases_passed": cases - len(failures),
        "case_seeds": case_seeds,
        "invariant_checks": invariant_checks,
        "max_candidates": max_candidates,
        "beam_width": beam_width,
        "success": not failures,
        "failures": [failure.as_dict() for failure in failures],
        "truth_boundary": (
            "This is deterministic property/fuzz evidence over generated valid MWS inputs and model/search invariants. "
            "It is not end-to-end benchmark evidence, production workload coverage, proof of universal correctness, "
            "or evidence of performance superiority."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic MORPHEUS property/fuzz invariants")
    parser.add_argument("--cases", type=int, default=DEFAULT_CASES)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--max-candidates", type=int, default=256)
    parser.add_argument("--beam-width", type=int, default=48)
    args = parser.parse_args()
    report = run_property_fuzz_campaign(
        cases=args.cases,
        seed=args.seed,
        max_candidates=args.max_candidates,
        beam_width=args.beam_width,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
