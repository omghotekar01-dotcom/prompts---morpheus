from __future__ import annotations

import hashlib
import json
import math
import statistics
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from .artifact_manifest import artifact_manifest_hash
from .engine import synthesize
from .generated_migration_benchmark import (
    GeneratedMigrationBenchmarkReport,
    MigrationBenchmarkConfig,
    benchmark_generated_migration_bundle,
)
from .generated_migration_benchmark_evidence import verify_generated_migration_benchmark_evidence
from .generated_migration_bundle import build_generated_migration_bundle, select_distinct_migration_pair
from .models import WorkloadSpec
from .research_suite import ExperimentManifest, FrozenExperiment, freeze_experiment_matrix


CAMPAIGN_SCHEMA = "morpheus-generated-migration-campaign-v1"
SUMMARY_SCHEMA = "morpheus-generated-migration-campaign-summary-v1"
SUPPORTED_PAIR_POLICY = "winner-to-best-distinct"
_REQUIRED_AXES = {
    "candidate_pair_policy",
    "readers",
    "record_count",
    "transitions",
    "workload_name",
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def freeze_generated_migration_campaign(matrix: Mapping[str, Any]) -> ExperimentManifest:
    """Freeze the RQ7 matrix and reject factors the v1 runner cannot execute.

    The benchmark harness is intentionally deterministic. The matrix therefore
    uses seed 0 as a protocol identity instead of pretending randomized sampling
    exists. A future randomized protocol must version this contract.
    """

    if str(matrix.get("study_id", "")) != "rq7-generated-migration-v1":
        raise ValueError("generated migration campaign requires study_id rq7-generated-migration-v1")
    axes = matrix.get("axes")
    if not isinstance(axes, Mapping) or set(axes) != _REQUIRED_AXES:
        raise ValueError(f"generated migration campaign axes must be exactly {sorted(_REQUIRED_AXES)}")
    seeds = [int(seed) for seed in matrix.get("seeds", [])]
    if seeds != [0]:
        raise ValueError("generated migration campaign v1 requires deterministic seed identity [0]")
    policies = list(axes["candidate_pair_policy"])
    if policies != [SUPPORTED_PAIR_POLICY]:
        raise ValueError(f"v1 supports only candidate_pair_policy={SUPPORTED_PAIR_POLICY!r}")

    return freeze_experiment_matrix(
        study_id=str(matrix["study_id"]),
        hypothesis=str(matrix["hypothesis"]),
        metric=str(matrix["metric"]),
        lower_is_better=bool(matrix["lower_is_better"]),
        repetitions=int(matrix["repetitions"]),
        seeds=seeds,
        axes=axes,
        max_experiments=int(matrix["max_experiments"]),
    )


@dataclass(frozen=True)
class GeneratedMigrationCampaignEntry:
    experiment_id: str
    factor_sha256: str
    factors: dict[str, Any]
    report_sha256: str
    report: GeneratedMigrationBenchmarkReport
    verified_total_reads: int | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "factor_sha256": self.factor_sha256,
            "factors": self.factors,
            "report_sha256": self.report_sha256,
            "report": self.report.as_dict(),
            "verified_total_reads": self.verified_total_reads,
        }


@dataclass(frozen=True)
class GeneratedMigrationCampaignReport:
    schema: str
    study_id: str
    manifest_sha256: str
    source_candidate_id: str
    target_candidate_id: str
    source_manifest_sha256: str
    target_manifest_sha256: str
    planned_experiments: int
    executed_experiments: int
    entries: tuple[GeneratedMigrationCampaignEntry, ...]
    complete: bool
    comparable_environment: bool
    evidence_state: str
    campaign_sha256: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "study_id": self.study_id,
            "manifest_sha256": self.manifest_sha256,
            "source_candidate_id": self.source_candidate_id,
            "target_candidate_id": self.target_candidate_id,
            "source_manifest_sha256": self.source_manifest_sha256,
            "target_manifest_sha256": self.target_manifest_sha256,
            "planned_experiments": self.planned_experiments,
            "executed_experiments": self.executed_experiments,
            "entries": [entry.as_dict() for entry in self.entries],
            "complete": self.complete,
            "comparable_environment": self.comparable_environment,
            "evidence_state": self.evidence_state,
            "campaign_sha256": self.campaign_sha256,
            "truth_boundary": (
                "The campaign binds a frozen RQ7 factor matrix to actual MORPHEUS-generated source/target configurations and "
                "their local transition-cost measurements. Completeness does not make CI-hosted timings publication-grade, "
                "does not establish cross-machine generalization, and does not establish cross-process hot replacement."
            ),
        }


BenchmarkFn = Callable[..., GeneratedMigrationBenchmarkReport]


def _config_for_experiment(experiment: FrozenExperiment, spec: WorkloadSpec) -> MigrationBenchmarkConfig:
    factors = experiment.factors
    if factors.get("workload_name") != spec.name:
        raise ValueError(
            f"experiment {experiment.experiment_id} targets workload {factors.get('workload_name')!r}, expected {spec.name!r}"
        )
    if factors.get("candidate_pair_policy") != SUPPORTED_PAIR_POLICY:
        raise ValueError("unsupported generated migration candidate-pair policy")
    return MigrationBenchmarkConfig(
        readers=int(factors["readers"]),
        transitions=int(factors["transitions"]),
        repetitions=int(experiment.repetitions),
        record_count=int(factors["record_count"]),
    )


def run_generated_migration_campaign(
    spec: WorkloadSpec,
    matrix: Mapping[str, Any],
    *,
    benchmark_fn: BenchmarkFn = benchmark_generated_migration_bundle,
    limit: int | None = None,
    compile_timeout_seconds: int = 120,
    run_timeout_seconds: int = 120,
) -> GeneratedMigrationCampaignReport:
    manifest = freeze_generated_migration_campaign(matrix)
    if limit is not None and (limit < 1 or limit > len(manifest.experiments)):
        raise ValueError("campaign limit must be within the frozen experiment count")
    if compile_timeout_seconds < 1 or run_timeout_seconds < 1:
        raise ValueError("campaign timeouts must be positive")

    synthesis = synthesize(spec)
    source, target = select_distinct_migration_pair(synthesis)
    bundle = build_generated_migration_bundle(spec, source, target, record_count=128)
    source_manifest_sha = artifact_manifest_hash(bundle.source_manifest)
    target_manifest_sha = artifact_manifest_hash(bundle.target_manifest)

    selected = manifest.experiments if limit is None else manifest.experiments[:limit]
    entries: list[GeneratedMigrationCampaignEntry] = []
    for experiment in selected:
        config = _config_for_experiment(experiment, spec)
        report = benchmark_fn(
            bundle,
            spec,
            config=config,
            compile_timeout_seconds=compile_timeout_seconds,
            run_timeout_seconds=run_timeout_seconds,
        )
        payload = report.as_dict()
        verified_total_reads: int | None = None
        if report.success:
            verified = verify_generated_migration_benchmark_evidence(payload)
            verified_total_reads = verified.total_reads
        entries.append(
            GeneratedMigrationCampaignEntry(
                experiment_id=experiment.experiment_id,
                factor_sha256=experiment.factor_sha256,
                factors=dict(experiment.factors),
                report_sha256=_sha256(payload),
                report=report,
                verified_total_reads=verified_total_reads,
            )
        )

    all_success = bool(entries) and all(entry.report.success for entry in entries)
    complete = len(entries) == len(manifest.experiments) and all_success
    states = {entry.report.evidence_state for entry in entries if entry.report.success}
    only_ci = states == {"MEASURED_CI_SMOKE_GENERATED_MIGRATION_TRANSITION_COST"}
    only_local = states == {"MEASURED_LOCAL_PROCESS_GENERATED_MIGRATION_TRANSITION_COST"}
    comparable = all_success and (only_ci or only_local)

    if not all_success:
        evidence_state = "GENERATED_MIGRATION_CAMPAIGN_INCOMPLETE_OR_FAILED"
    elif len(entries) < len(manifest.experiments):
        evidence_state = "GENERATED_MIGRATION_CAMPAIGN_PARTIAL_VERIFIED"
    elif only_ci:
        evidence_state = "GENERATED_MIGRATION_CAMPAIGN_COMPLETE_CI_SMOKE"
    elif only_local:
        evidence_state = "GENERATED_MIGRATION_CAMPAIGN_COMPLETE_LOCAL_MEASUREMENTS"
    else:
        evidence_state = "GENERATED_MIGRATION_CAMPAIGN_COMPLETE_MIXED_ENVIRONMENT_NOT_COMPARABLE"

    hash_core = {
        "schema": CAMPAIGN_SCHEMA,
        "study_id": manifest.study_id,
        "manifest_sha256": manifest.manifest_sha256,
        "source_candidate_id": source.id,
        "target_candidate_id": target.id,
        "source_manifest_sha256": source_manifest_sha,
        "target_manifest_sha256": target_manifest_sha,
        "entries": [
            {
                "experiment_id": entry.experiment_id,
                "factor_sha256": entry.factor_sha256,
                "report_sha256": entry.report_sha256,
            }
            for entry in entries
        ],
    }
    return GeneratedMigrationCampaignReport(
        schema=CAMPAIGN_SCHEMA,
        study_id=manifest.study_id,
        manifest_sha256=manifest.manifest_sha256,
        source_candidate_id=source.id,
        target_candidate_id=target.id,
        source_manifest_sha256=source_manifest_sha,
        target_manifest_sha256=target_manifest_sha,
        planned_experiments=len(manifest.experiments),
        executed_experiments=len(entries),
        entries=tuple(entries),
        complete=complete,
        comparable_environment=comparable,
        evidence_state=evidence_state,
        campaign_sha256=_sha256(hash_core),
    )


def _quantile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise ValueError("cannot summarize an empty metric")
    ordered = sorted(float(value) for value in values)
    if probability <= 0:
        return ordered[0]
    if probability >= 1:
        return ordered[-1]
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _metric_summary(values: Sequence[float]) -> dict[str, float | int]:
    if not values:
        raise ValueError("metric summary requires at least one observation")
    numeric = [float(value) for value in values]
    return {
        "n": len(numeric),
        "mean": statistics.fmean(numeric),
        "median": statistics.median(numeric),
        "stdev": statistics.stdev(numeric) if len(numeric) > 1 else 0.0,
        "min": min(numeric),
        "p95": _quantile(numeric, 0.95),
        "p99": _quantile(numeric, 0.99),
        "max": max(numeric),
    }


def summarize_generated_migration_campaign(campaign: GeneratedMigrationCampaignReport) -> dict[str, Any]:
    """Produce descriptive transition-cost summaries without inferential claims."""

    groups: list[dict[str, Any]] = []
    successful_entries = [entry for entry in campaign.entries if entry.report.success]
    for entry in successful_entries:
        rows = entry.report.rows
        migrate = [row.migrate_validate_activate_ns_per for row in rows]
        rollback = [row.rollback_ns_per for row in rows]
        round_trip = [
            row.migrate_validate_activate_ns_per + row.rollback_ns_per
            for row in rows
        ]
        total_reads = sum(row.reads for row in rows)
        invalid_reads = sum(row.invalid_reads for row in rows)
        groups.append(
            {
                "experiment_id": entry.experiment_id,
                "factors": dict(entry.factors),
                "migrate_validate_activate_ns_per": _metric_summary(migrate),
                "rollback_ns_per": _metric_summary(rollback),
                "round_trip_transition_ns_per": _metric_summary(round_trip),
                "total_reader_observations": total_reads,
                "invalid_reader_observations": invalid_reads,
            }
        )

    return {
        "schema": SUMMARY_SCHEMA,
        "study_id": campaign.study_id,
        "manifest_sha256": campaign.manifest_sha256,
        "campaign_sha256": campaign.campaign_sha256,
        "campaign_evidence_state": campaign.evidence_state,
        "successful_experiments": len(successful_entries),
        "executed_experiments": campaign.executed_experiments,
        "planned_experiments": campaign.planned_experiments,
        "groups": groups,
        "evidence_state": "DESCRIPTIVE_SUMMARY_OF_GENERATED_MIGRATION_CAMPAIGN",
        "truth_boundary": (
            "This summary reports descriptive local timing distributions only. It performs no hypothesis test, no multiple-comparison "
            "correction and no cross-machine normalization, and therefore cannot by itself support a publication-grade superiority claim."
        ),
    }
