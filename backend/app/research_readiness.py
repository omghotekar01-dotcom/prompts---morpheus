from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResearchFeatureState:
    feature: str
    implementation_state: str
    evidence_scope: str
    automatic_control_allowed: bool
    blocker: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "feature": self.feature,
            "implementation_state": self.implementation_state,
            "evidence_scope": self.evidence_scope,
            "automatic_control_allowed": self.automatic_control_allowed,
            "blocker": self.blocker,
        }


def distribution_research_readiness() -> dict[str, object]:
    """Truthful readiness ledger for skew/trace-aware MORPHEUS research.

    This deliberately separates implemented analysis mechanics from evidence
    required to authorize an autonomous runtime decision.
    """

    features = (
        ResearchFeatureState(
            feature="typed_access_distribution_mws_ir",
            implementation_state="IMPLEMENTED_TESTED",
            evidence_scope="SEMANTIC_WORKLOAD_REPRESENTATION",
            automatic_control_allowed=True,
        ),
        ResearchFeatureState(
            feature="generated_candidate_distribution_execution",
            implementation_state="IMPLEMENTED_TESTED_PROVENANCE_BOUND",
            evidence_scope="LOCAL_END_TO_END_CANDIDATE_MEASUREMENT",
            automatic_control_allowed=True,
            blocker="measurement remains machine-local unless executed under the frozen controlled-hardware protocol",
        ),
        ResearchFeatureState(
            feature="distribution_aware_primitive_cost_calibration",
            implementation_state="NOT_IMPLEMENTED",
            evidence_scope="UNIFORM_PRIMITIVE_CALIBRATION_ONLY",
            automatic_control_allowed=False,
            blocker="nonuniform primitive calibration matrix and held-out validation are required",
        ),
        ResearchFeatureState(
            feature="runtime_distribution_mix_drift",
            implementation_state="IMPLEMENTED_TESTED_OPTIONAL_TELEMETRY",
            evidence_scope="OPERATOR_OR_INSTRUMENTATION_SUPPLIED_DISTRIBUTION_MIX",
            automatic_control_allowed=True,
            blocker="decision remains predicted control-plane recommendation until migration/data-plane gates pass",
        ),
        ResearchFeatureState(
            feature="access_trace_characterization",
            implementation_state="IMPLEMENTED_RESEARCH_HEURISTIC",
            evidence_scope="FINITE_TRACE_DESCRIPTIVE_METRICS",
            automatic_control_allowed=False,
            blocker="requires validation on independent real traces and calibrated model-selection criteria",
        ),
        ResearchFeatureState(
            feature="access_trace_window_drift",
            implementation_state="IMPLEMENTED_RESEARCH_METRICS",
            evidence_scope="FINITE_WINDOW_TV_JS_AND_HOTSET_OVERLAP",
            automatic_control_allowed=False,
            blocker="thresholds are not calibrated for online false-positive/false-negative control",
        ),
        ResearchFeatureState(
            feature="rolling_trace_phase_candidates",
            implementation_state="IMPLEMENTED_RESEARCH_EXPLORATORY",
            evidence_scope="ADJACENT_FINITE_WINDOW_THRESHOLD_CROSSINGS",
            automatic_control_allowed=False,
            blocker="requires statistically calibrated change-point protocol and temporal holdout evaluation",
        ),
        ResearchFeatureState(
            feature="trace_classifier_synthetic_evaluation",
            implementation_state="IMPLEMENTED_SYNTHETIC_GENERATOR_EVALUATION",
            evidence_scope="MORPHEUS_OWNED_SYNTHETIC_FAMILIES",
            automatic_control_allowed=False,
            blocker="synthetic accuracy is not real-workload generalization evidence",
        ),
    )

    promotion_blockers = sorted(
        {
            item.blocker
            for item in features
            if not item.automatic_control_allowed and item.blocker is not None
        }
    )
    return {
        "schema": "morpheus-distribution-research-readiness-v1",
        "features": [item.as_dict() for item in features],
        "automatic_control_research_features": [
            item.feature for item in features if item.automatic_control_allowed
        ],
        "restricted_research_features": [
            item.feature for item in features if not item.automatic_control_allowed
        ],
        "promotion_blockers": promotion_blockers,
        "evidence_state": "IMPLEMENTATION_AND_PROMOTION_BOUNDARIES_DECLARED",
        "truth_boundary": (
            "A feature being implemented does not imply its statistical assumptions or performance claims are validated. "
            "Restricted research features must not be converted into autonomous runtime-control inputs until their stated blockers are resolved with independent evidence."
        ),
    }
