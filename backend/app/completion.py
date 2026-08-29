from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class Gate:
    id: str
    description: str
    capability: str
    accepted_values: frozenset[str]


@dataclass(frozen=True)
class PhaseDefinition:
    id: str
    name: str
    gates: tuple[Gate, ...]


IMPLEMENTED_PREFIXES = ("IMPLEMENTED", "TESTED", "MEASURED", "VALIDATED")


def _implemented(value: str) -> bool:
    return any(value.startswith(prefix) for prefix in IMPLEMENTED_PREFIXES)


PHASES: tuple[PhaseDefinition, ...] = (
    PhaseDefinition(
        "P1",
        "Typed workload specification and synthesis API",
        (
            Gate("mws", "Typed MWS validation is tested", "mws", frozenset()),
            Gate("search", "Deterministic search is tested", "deterministic_search", frozenset()),
        ),
    ),
    PhaseDefinition(
        "P2",
        "C++ primitive laboratory",
        (
            Gate("bplus", "Real B+ tree primitive is present", "bplus_tree_primitive", frozenset()),
            Gate("core-ci", "C++20 core CI is configured", "windows_msvc_cpp20_ci", frozenset()),
            Gate("sanitizers", "ASan/UBSan core gate is configured", "core_sanitizer_gate", frozenset()),
        ),
    ),
    PhaseDefinition(
        "P3",
        "Generated artifact and correctness gates",
        (
            Gate("codegen", "C++20 artifact generation is tested", "artifact_codegen", frozenset()),
            Gate("compile", "Generated artifacts have a compile gate", "artifact_compile_gate", frozenset()),
            Gate("differential", "Generated artifacts have a stateful differential gate", "artifact_stateful_differential_gate", frozenset()),
        ),
    ),
    PhaseDefinition(
        "P4",
        "Evidence identity and safe upgrade policy",
        (
            Gate("feature-policy", "Versioned feature policy fails closed for blocked/research control", "feature_policy_registry", frozenset()),
            Gate("distribution-identity", "Calibration measurements are bound to exact implementation, operation, scale and distribution", "distribution_bound_calibration", frozenset()),
            Gate("workload-coverage", "Workload calibration coverage distinguishes distribution, scale, stale and missing evidence", "workload_calibration_coverage", frozenset()),
            Gate("mutation-cost", "Mutation maintenance cost consumes only exact operation/distribution evidence", "distribution_aware_mutation_cost", frozenset()),
            Gate("api-fingerprint", "Versioned route contract fingerprint is available for compatibility checks", "api_contract_fingerprint", frozenset()),
        ),
    ),
    PhaseDefinition(
        "P5",
        "Calibration and benchmark science",
        (
            Gate("calibration", "Calibration import is tested", "calibration_import", frozenset()),
            Gate("durable-calibration", "Calibration profiles persist", "calibration_persistence", frozenset()),
            Gate("distribution-matrix", "Distribution-bound calibration matrix has a tested CI smoke and research harness", "distribution_calibration_matrix", frozenset()),
            Gate("baseline", "Paired standard-library baseline matrix exists", "paired_baseline_matrix", frozenset()),
        ),
    ),
    PhaseDefinition(
        "P6",
        "Composite search and Pareto synthesis",
        (
            Gate("beam", "Beam search is tested", "beam_search", frozenset()),
            Gate("pareto", "Pareto synthesis is tested", "pareto_front", frozenset()),
            Gate("oracle", "Search-quality oracle evaluation is tested", "search_quality_oracle_evaluation", frozenset()),
        ),
    ),
    PhaseDefinition(
        "P7",
        "Runtime adaptation",
        (
            Gate("drift", "Runtime drift detection is tested", "runtime_drift_detection", frozenset()),
            Gate("migration", "Gated migration controller exists", "runtime_gated_migration", frozenset()),
            Gate("dataplane", "Versioned local data-plane activation/rollback exists", "local_dataplane_swap", frozenset()),
        ),
    ),
    PhaseDefinition(
        "P8",
        "Production-oriented control plane",
        (
            Gate("persistence", "Run metadata persists", "persistent_run_metadata", frozenset()),
            Gate("ledger", "Tamper-evident evidence ledger exists", "tamper_evident_evidence_ledger", frozenset()),
            Gate("security", "API key/rate-limit policy exists", "optional_api_key_and_rate_limit", frozenset()),
            Gate("worker", "Bounded no-shell worker exists", "bounded_local_worker", frozenset()),
        ),
    ),
    PhaseDefinition(
        "P9",
        "Evidence-grounded Copilot",
        (
            Gate("evidence-copilot", "Deterministic evidence mode is implemented", "copilot_evidence_mode", frozenset()),
            Gate("language-boundary", "LLM authority remains explicitly separated", "copilot_llm", frozenset({"NOT_IMPLEMENTED", "OPTIONAL_TOOL_RESTRICTED"})),
        ),
    ),
    PhaseDefinition(
        "P10",
        "Research experiment suite",
        (
            Gate("heldout", "Held-out prediction evaluator is tested", "heldout_prediction_evaluation", frozenset()),
            Gate("search-quality", "Beam-vs-exhaustive evaluator is tested", "search_quality_oracle_evaluation", frozenset()),
            Gate("baseline-matrix", "Paired baseline matrix runner exists", "paired_baseline_matrix", frozenset()),
            Gate("research-suite", "Frozen experiment/statistics suite is tested", "research_experiment_suite", frozenset()),
        ),
    ),
    PhaseDefinition(
        "P11",
        "Evidence-gated release package",
        (
            Gate("claim-gate", "Release claim gate exists", "release_claim_gate", frozenset()),
            Gate("package", "Deterministic evidence package builder is tested", "release_evidence_package", frozenset()),
            Gate("distribution-provenance", "Distribution calibration release evidence is structurally validated and hash-linked", "distribution_release_provenance", frozenset()),
            Gate("repro", "Reproducibility manifest exists", "reproducibility_manifest", frozenset()),
            Gate("contract-repro", "Strict release reproducibility binds exact commit, API contract and feature policy", "contract_bound_reproducibility", frozenset()),
        ),
    ),
    PhaseDefinition(
        "P12",
        "Canonical specification and repository continuity",
        (
            Gate(
                "prompt-corpus",
                "The exact canonical 39-prompt Engineering Bible and final-entry references are test-enforced",
                "prompt_corpus_integrity",
                frozenset(),
            ),
        ),
    ),
)


def _gate_passed(gate: Gate, capabilities: Mapping[str, Any]) -> tuple[bool, str]:
    raw = capabilities.get(gate.capability)
    value = "MISSING" if raw is None else str(raw)
    if gate.accepted_values:
        return value in gate.accepted_values, value
    return _implemented(value), value


def engineering_completion_report(capabilities: Mapping[str, Any]) -> dict[str, Any]:
    """Compute deterministic engineering-gate completion from explicit capabilities.

    This report intentionally excludes scientific publication, patent/legal
    outcomes, independent validation, external deployment/customer evidence,
    certifications and universal performance superiority. Those outcomes cannot
    be inferred from repository code, prompt files or CI alone.
    """

    phases: list[dict[str, Any]] = []
    total = 0
    passed_total = 0
    for phase in PHASES:
        gates: list[dict[str, Any]] = []
        for gate in phase.gates:
            passed, value = _gate_passed(gate, capabilities)
            total += 1
            passed_total += int(passed)
            gates.append(
                {
                    "id": gate.id,
                    "description": gate.description,
                    "capability": gate.capability,
                    "value": value,
                    "passed": passed,
                }
            )
        passed_count = sum(int(item["passed"]) for item in gates)
        phase_total = len(gates)
        phases.append(
            {
                "id": phase.id,
                "name": phase.name,
                "passed_gates": passed_count,
                "total_gates": phase_total,
                "engineering_percent": round(100.0 * passed_count / phase_total, 1) if phase_total else 100.0,
                "state": "ENGINEERING_GATES_COMPLETE" if passed_count == phase_total else "ENGINEERING_GATES_INCOMPLETE",
                "gates": gates,
            }
        )

    return {
        "schema": "morpheus-engineering-completion-v1",
        "passed_gates": passed_total,
        "total_gates": total,
        "engineering_percent": round(100.0 * passed_total / total, 1) if total else 100.0,
        "phases": phases,
        "excluded_outcomes": [
            "publication acceptance",
            "patent filing/grant or freedom-to-operate",
            "independent benchmark validation",
            "production deployment at external organizations",
            "customer traction or commercial validation",
            "security/regulatory certification",
            "universal state-of-the-art superiority",
        ],
        "truth_note": (
            "Completion percentage is a deterministic count of explicitly enumerated repository engineering gates only; "
            "it is not a scientific, legal, commercial, certification or external-validation score."
        ),
    }