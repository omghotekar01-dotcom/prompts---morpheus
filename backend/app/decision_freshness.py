from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable


SCHEMA = "morpheus-decision-freshness-passport-v1"


def _sha256_json(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _window_sha256(keys: Iterable[int]) -> str:
    return _sha256_json(list(keys))


def _unique_gates(doctor: dict[str, Any]) -> list[str]:
    gates: list[str] = []
    playbook = doctor.get("migration_playbook")
    if isinstance(playbook, list):
        for item in playbook:
            if not isinstance(item, dict):
                continue
            gate = item.get("gate")
            if isinstance(gate, str) and gate and gate not in gates:
                gates.append(gate)
    return gates


def build_decision_freshness_passport(
    *,
    source_spec_hash: str,
    query_index: int,
    current_structure: str,
    baseline_keys: list[int],
    observed_keys: list[int],
    drift: dict[str, Any],
    baseline: dict[str, Any],
    observed: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    """Bind one recommendation-validity decision to the exact supplied evidence.

    This is evidence/change-control metadata only. It intentionally does not
    create a time-based expiry, claim that finite windows represent future
    traffic, or authorize a production rollout.
    """

    action = str(decision.get("action") or "")
    candidate_changed = bool(decision.get("candidate_changed"))
    route_changed = bool(decision.get("route_primitive_changed"))
    distribution_changed = bool(decision.get("distribution_label_changed"))
    drifted = bool(drift.get("drifted"))

    if action == "BLOCKED_OBSERVED_WORKLOAD_INFEASIBLE":
        freshness_state = "BLOCKED_OBSERVED_WORKLOAD_INFEASIBLE"
        rollout_disposition = "DO_NOT_ROLLOUT_RESOLVE_CONSTRAINTS"
        summary = "The observed finite window produces no feasible modeled candidate under the declared constraints."
    elif candidate_changed or route_changed:
        freshness_state = "SUPERSEDED_FOR_SUPPLIED_WINDOWS"
        rollout_disposition = "HOLD_PRIOR_DECISION_REVALIDATE_OBSERVED_CANDIDATE"
        summary = "The prior modeled recommendation is no longer current for the supplied observed window."
    elif drifted or distribution_changed:
        freshness_state = "REVIEW_REQUIRED_AFTER_DRIFT"
        rollout_disposition = "HOLD_AND_REMEASURE_CURRENT_RECOMMENDATION"
        summary = "The modeled recommendation stayed stable, but the supplied access evidence changed enough to require remeasurement."
    else:
        freshness_state = "CURRENT_FOR_SUPPLIED_WINDOWS"
        rollout_disposition = "NO_CHANGE_REQUIRED_CONTINUE_MONITORING"
        summary = "The recommendation remained stable for the supplied finite baseline and observed windows."

    baseline_doctor = baseline.get("doctor") if isinstance(baseline.get("doctor"), dict) else {}
    observed_doctor = observed.get("doctor") if isinstance(observed.get("doctor"), dict) else {}
    required_gates = _unique_gates(observed_doctor)
    if freshness_state != "CURRENT_FOR_SUPPLIED_WINDOWS":
        for gate in (
            "OBSERVED_WORKLOAD_REVIEW_REQUIRED",
            "TARGET_MACHINE_REMEASUREMENT_REQUIRED",
            "FRESH_TRACE_REVALIDATION_BEFORE_CUTOVER",
        ):
            if gate not in required_gates:
                required_gates.append(gate)

    evidence_binding = {
        "source_spec_hash": source_spec_hash,
        "query_index": query_index,
        "current_structure": current_structure,
        "baseline_window_sha256": _window_sha256(baseline_keys),
        "observed_window_sha256": _window_sha256(observed_keys),
        "baseline_sample_count": len(baseline_keys),
        "observed_sample_count": len(observed_keys),
        "baseline_draft_spec_hash": baseline.get("draft_spec_hash"),
        "observed_draft_spec_hash": observed.get("draft_spec_hash"),
        "baseline_winner_candidate_id": baseline.get("winner_candidate_id"),
        "observed_winner_candidate_id": observed.get("winner_candidate_id"),
        "baseline_route_primitive": baseline.get("route_primitive"),
        "observed_route_primitive": observed.get("route_primitive"),
    }

    change_ticket = {
        "freshness_state": freshness_state,
        "rollout_disposition": rollout_disposition,
        "required_evidence_gates": required_gates,
        "stages": [
            {
                "id": "freeze",
                "title": "Freeze the prior decision",
                "required": freshness_state != "CURRENT_FOR_SUPPLIED_WINDOWS",
                "action": (
                    "Do not advance a prior recommendation while the observed evidence is blocked, superseded, or awaiting remeasurement."
                    if freshness_state != "CURRENT_FOR_SUPPLIED_WINDOWS"
                    else "No migration is requested by this watch result; keep monitoring the accepted implementation."
                ),
            },
            {
                "id": "remeasure",
                "title": "Measure on the target machine",
                "required": freshness_state != "CURRENT_FOR_SUPPLIED_WINDOWS",
                "action": "Measure the observed modeled finalist(s) under the accepted workload contract before making a quantitative performance claim.",
            },
            {
                "id": "verify",
                "title": "Verify generated artifacts",
                "required": freshness_state in {
                    "SUPERSEDED_FOR_SUPPLIED_WINDOWS",
                    "REVIEW_REQUIRED_AFTER_DRIFT",
                },
                "action": "Compile and behavior-verify the exact generated artifact and retain its content/configuration/workload hashes.",
            },
            {
                "id": "shadow",
                "title": "Shadow before ownership transfer",
                "required": freshness_state == "SUPERSEDED_FOR_SUPPLIED_WINDOWS",
                "action": "Feed bounded representative input to old and proposed implementations without transferring production ownership.",
            },
            {
                "id": "human_cutover",
                "title": "Use a reversible human-approved cutover",
                "required": freshness_state == "SUPERSEDED_FOR_SUPPLIED_WINDOWS",
                "action": "Only after all gates pass, use an operator-defined feature flag or controlled release; MORPHEUS does not auto-advance rollout stages.",
            },
        ],
        "stop_conditions": [
            "Any correctness or shadow-result mismatch.",
            "Generated-artifact compile or behavior verification failure.",
            "Target-machine measurement does not satisfy operator-defined acceptance criteria.",
            "A newer representative trace window changes the modeled recommendation before cutover.",
            "Evidence-ledger or artifact-integrity verification fails.",
            "The previous implementation or a verified reverse path is not available for rollback.",
        ],
        "rollback_requirements": [
            "Preserve the previous implementation until the operator closes the rollout window.",
            "Keep cutover behind an operator-controlled reversible switch or release mechanism.",
            "Capture the pre-cutover workload/artifact/evidence identities used for the decision.",
            "For stateful transformations, require a separately verified reverse migration or restorable snapshot before ownership transfer.",
        ],
        "automatic_stage_advance_allowed": False,
        "automatic_cutover_allowed": False,
    }

    identity_payload = {
        "schema": SCHEMA,
        "freshness_state": freshness_state,
        "rollout_disposition": rollout_disposition,
        "evidence_binding": evidence_binding,
        "decision": {
            "action": action,
            "candidate_changed": candidate_changed,
            "route_primitive_changed": route_changed,
            "distribution_label_changed": distribution_changed,
            "drifted": drifted,
        },
        "required_evidence_gates": required_gates,
    }

    return {
        "schema": SCHEMA,
        "passport_sha256": _sha256_json(identity_payload),
        "freshness_state": freshness_state,
        "rollout_disposition": rollout_disposition,
        "summary": summary,
        "evidence_binding": evidence_binding,
        "change_ticket": change_ticket,
        "baseline_launch_state": baseline_doctor.get("launch_state"),
        "observed_launch_state": observed_doctor.get("launch_state"),
        "eligible_for_runtime_automatic_control": False,
        "truth_boundary": (
            "This passport is scoped to the exact supplied MWS and finite trace windows identified by the hashes above. "
            "It is not a clock-based expiry, calibrated online change-point guarantee, proof that the observed window represents future traffic, "
            "measured speedup claim, or production deployment authorization. Any rollout remains human-controlled and gated by target-machine measurement, "
            "artifact verification, correctness/shadow comparison, fresh-workload revalidation, and a separately preserved rollback path."
        ),
    }
