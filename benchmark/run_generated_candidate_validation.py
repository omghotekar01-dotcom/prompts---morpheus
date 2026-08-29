#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.candidate_benchmark import benchmark_generated_candidate  # noqa: E402
from app.candidate_validation import build_candidate_validation_point  # noqa: E402
from app.engine import synthesize  # noqa: E402
from app.heldout_evaluation import HeldoutCandidateMeasurement, evaluate_heldout_candidate_groups  # noqa: E402
from app.models import SearchStrategy, WorkloadSpec  # noqa: E402
from app.parser import parse_workload_text, semantic_hash  # noqa: E402
from app.workload_ir import lower_and_hash_workload_ir  # noqa: E402


DISTRIBUTION_PROTOCOL = "morpheus-access-distribution-v1"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _write_json(path: Path, payload: Any) -> str:
    rendered = json.dumps(payload, sort_keys=True, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")
    return _sha256_bytes(rendered.encode("utf-8"))


def _effective_spec(raw: str, record_count_override: int | None) -> WorkloadSpec:
    spec = parse_workload_text(raw)
    if record_count_override is None:
        return spec
    payload = spec.model_dump(mode="json")
    payload["record_count"] = record_count_override
    return WorkloadSpec.model_validate(payload)


def _query_distribution_provenance(spec: WorkloadSpec) -> list[dict[str, Any]]:
    return [
        {
            "query_index": index,
            "query_kind": query.kind.value,
            "field": query.field,
            **query.distribution.model_dump(mode="json", exclude_none=True),
        }
        for index, query in enumerate(spec.queries)
    ]


def run_campaign(
    spec_paths: list[Path],
    *,
    output_dir: Path,
    top_candidates: int,
    record_count_override: int | None,
    operations: int,
    repetitions: int,
    warmup: int,
    max_candidates: int,
    beam_width: int,
) -> dict[str, Any]:
    if not spec_paths:
        raise ValueError("at least one MWS path is required")
    if top_candidates < 1:
        raise ValueError("top_candidates must be positive")
    if record_count_override is not None and record_count_override < 1:
        raise ValueError("record_count_override must be positive")
    if operations < 1 or repetitions < 1 or warmup < 0:
        raise ValueError("operations/repetitions must be positive and warmup non-negative")

    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "candidate-runs"
    raw_dir.mkdir(parents=True, exist_ok=True)

    manifest_workloads: list[dict[str, Any]] = []
    validation_rows: list[dict[str, Any]] = []
    grouped_measurements: dict[str, list[HeldoutCandidateMeasurement]] = defaultdict(list)

    for spec_path in spec_paths:
        resolved = spec_path.resolve()
        raw = resolved.read_text(encoding="utf-8")
        spec = _effective_spec(raw, record_count_override)
        _ir, workload_ir_hash = lower_and_hash_workload_ir(spec)
        synthesis = synthesize(
            spec,
            strategy=SearchStrategy.AUTO,
            max_candidates=max_candidates,
            beam_width=beam_width,
        )
        feasible = [candidate for candidate in synthesis.candidates if candidate.feasible]
        selected = feasible[:top_candidates]
        workload_entry: dict[str, Any] = {
            "source_file": str(resolved),
            "source_file_sha256": _sha256_file(resolved),
            "workload_name": spec.name,
            "effective_spec_hash": semantic_hash(spec),
            "workload_ir_hash": workload_ir_hash,
            "effective_record_count": spec.record_count,
            "source_record_count_overridden": record_count_override is not None,
            "distribution_protocol": DISTRIBUTION_PROTOCOL,
            "query_distributions": _query_distribution_provenance(spec),
            "search_summary": synthesis.search_summary.model_dump(mode="json") if synthesis.search_summary else None,
            "selected_candidate_ids": [candidate.id for candidate in selected],
            "candidate_runs": [],
        }
        if len(selected) < 2:
            workload_entry["ranking_exclusion_reason"] = (
                "fewer than two feasible measured candidates selected; workload cannot contribute to ranking metrics"
            )

        for rank, candidate in enumerate(selected, start=1):
            benchmark = benchmark_generated_candidate(
                spec,
                candidate,
                record_count=spec.record_count,
                operations=operations,
                repetitions=repetitions,
                warmup=warmup,
            )
            raw_name = f"{spec.name}-rank{rank}-{candidate.id}.json"
            raw_path = raw_dir / raw_name
            raw_sha = _write_json(raw_path, benchmark.as_dict())
            run_entry: dict[str, Any] = {
                "rank": rank,
                "candidate_id": candidate.id,
                "predicted_latency_us": candidate.predicted_latency_us,
                "prediction_source": candidate.prediction_source,
                "uncertainty_ratio": candidate.uncertainty_ratio,
                "benchmark_file": str(raw_path.relative_to(output_dir)),
                "benchmark_file_sha256": raw_sha,
                "success": benchmark.success,
                "evidence_state": benchmark.evidence_state,
                "configuration_ir_hash": benchmark.configuration_ir_hash,
                "distribution_protocol": benchmark.distribution_protocol,
                "query_distributions": list(benchmark.query_distributions),
            }
            if benchmark.success:
                point = build_candidate_validation_point(
                    spec,
                    candidate,
                    benchmark,
                    workload_id=spec.name,
                )
                point_payload = point.as_dict()
                run_entry["validation"] = point_payload
                validation_rows.append(point_payload)
                grouped_measurements[spec.name].append(
                    HeldoutCandidateMeasurement(
                        workload_id=spec.name,
                        candidate_id=candidate.id,
                        predicted=point.predicted_query_latency_us,
                        measured=point.measured_weighted_query_latency_us,
                    )
                )
            else:
                run_entry["failure"] = {
                    "compile_returncode": benchmark.compile_returncode,
                    "run_returncode": benchmark.run_returncode,
                    "compile_stderr_tail": benchmark.compile_stderr[-2000:],
                    "run_stderr_tail": benchmark.run_stderr[-2000:],
                }
            workload_entry["candidate_runs"].append(run_entry)

        manifest_workloads.append(workload_entry)

    csv_path = output_dir / "validation-points.csv"
    fieldnames = [
        "workload_id",
        "candidate_id",
        "predicted_query_latency_us",
        "measured_weighted_query_latency_us",
        "absolute_error_us",
        "relative_error",
        "benchmark_configuration_ir_hash",
        "evidence_state",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in validation_rows:
            writer.writerow({key: row.get(key) for key in fieldnames})

    ranking_measurements = [
        measurement
        for workload_id in sorted(grouped_measurements)
        if len(grouped_measurements[workload_id]) >= 2
        for measurement in grouped_measurements[workload_id]
    ]
    ranking_payload: dict[str, Any] | None = None
    if ranking_measurements:
        ranking_payload = evaluate_heldout_candidate_groups(
            ranking_measurements,
            top_k=min(top_candidates, 3),
            bootstrap_rounds=2000,
            bootstrap_seed=1337,
        ).as_dict()
        _write_json(output_dir / "heldout-ranking-evaluation.json", ranking_payload)

    manifest = {
        "schema": "morpheus-generated-candidate-validation-campaign-v1",
        "created_at": datetime.now(UTC).isoformat(),
        "distribution_protocol": DISTRIBUTION_PROTOCOL,
        "parameters": {
            "top_candidates": top_candidates,
            "record_count_override": record_count_override,
            "operations": operations,
            "repetitions": repetitions,
            "warmup": warmup,
            "max_candidates": max_candidates,
            "beam_width": beam_width,
        },
        "workloads": manifest_workloads,
        "validation_point_count": len(validation_rows),
        "ranking_workload_count": len({item.workload_id for item in ranking_measurements}),
        "ranking_evaluation_available": ranking_payload is not None,
        "evidence_state": "LOCAL_GENERATED_CANDIDATE_VALIDATION_CAMPAIGN",
        "truth_boundary": (
            "The campaign preserves predicted and measured generated-candidate evidence, including declared access-distribution provenance, on the executing machine. "
            "CI or uncontrolled workstation measurements remain exploratory and cannot be promoted to publication-grade performance claims."
        ),
    }
    manifest_path = output_dir / "manifest.json"
    manifest_sha = _write_json(manifest_path, manifest)

    artifact_files = sorted(path for path in output_dir.rglob("*") if path.is_file() and path.name != "evidence-index.json")
    evidence_index = {
        "schema": "morpheus-generated-candidate-validation-evidence-index-v1",
        "manifest_sha256": manifest_sha,
        "artifacts": [
            {
                "path": str(path.relative_to(output_dir)),
                "sha256": _sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
            for path in artifact_files
        ],
        "evidence_state": "CONTENT_HASHED_LOCAL_RESEARCH_PACKAGE",
    }
    _write_json(output_dir / "evidence-index.json", evidence_index)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark top generated MORPHEUS candidates and evaluate predicted-vs-measured ranking quality."
    )
    parser.add_argument("specs", nargs="+", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--top-candidates", type=int, default=3)
    parser.add_argument("--record-count", type=int)
    parser.add_argument("--ops", type=int, default=2000)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--max-candidates", type=int, default=4096)
    parser.add_argument("--beam-width", type=int, default=128)
    args = parser.parse_args()
    try:
        manifest = run_campaign(
            args.specs,
            output_dir=args.output_dir.resolve(),
            top_candidates=args.top_candidates,
            record_count_override=args.record_count,
            operations=args.ops,
            repetitions=args.repetitions,
            warmup=args.warmup,
            max_candidates=args.max_candidates,
            beam_width=args.beam_width,
        )
    except (OSError, TypeError, ValueError, RuntimeError) as exc:
        print(f"morpheus generated candidate validation: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({
        "manifest": str((args.output_dir.resolve() / 'manifest.json')),
        "validation_point_count": manifest["validation_point_count"],
        "ranking_evaluation_available": manifest["ranking_evaluation_available"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
