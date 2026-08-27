from __future__ import annotations

from typing import Any

from .models import SynthesisResult, WorkloadSpec
from .parser import canonical_dict


CERTIFICATE_SCHEMA = "morpheus-decision-certificate-v1"


def build_decision_certificate(
    *,
    run_id: str,
    spec: WorkloadSpec,
    result: SynthesisResult,
) -> dict[str, Any]:
    """Build the immutable claim boundary for one synthesis decision.

    The certificate intentionally contains the exact workload contract, search
    provenance, selected candidate facts and evidence labels needed to explain a
    decision later. It does not convert predictions into measurements and does
    not claim that compile/behavior gates ran merely because synthesis finished.
    """

    winner = result.winner.model_dump(mode="json") if result.winner else None
    search = result.search_summary.model_dump(mode="json") if result.search_summary else None
    return {
        "schema": CERTIFICATE_SCHEMA,
        "run_id": run_id,
        "spec_hash": result.spec_hash,
        "workload": canonical_dict(spec),
        "evidence_state": result.evidence_state,
        "active_calibration_profile": result.active_calibration_profile,
        "search_summary": search,
        "winner": winner,
        "pareto_candidate_ids": [candidate.id for candidate in result.pareto_front],
        "evaluated_candidate_count": len(result.candidates),
        "warnings": list(result.warnings),
        "explanation": list(result.explanation),
        "claim_boundary": {
            "performance_numbers_are_predictions": True,
            "synthesis_alone_proves_compile": False,
            "synthesis_alone_proves_behavioral_correctness": False,
            "synthesis_alone_proves_end_to_end_performance": False,
            "hard_constraints_silently_relaxed": False,
            "real_runtime_hot_swap_proven": False,
        },
        "required_followup_evidence": [
            "generated artifact content hash",
            "compile verification manifest",
            "stateful differential correctness manifest",
            "target-machine benchmark evidence before quantitative performance claims",
        ],
    }
