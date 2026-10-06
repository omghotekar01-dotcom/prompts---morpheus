from __future__ import annotations

from copy import deepcopy
from typing import Any

import yaml

from .access_trace import analyze_access_trace
from .access_trace_drift import compare_access_trace_windows
from .engine import DEFAULT_BEAM_WIDTH, DEFAULT_MAX_CANDIDATES, synthesize
from .hot_path_doctor import diagnose_hot_path
from .models import AccessDistribution, SearchStrategy
from .parser import SpecParseError, parse_workload_document


def _distribution_payload(analysis) -> dict[str, object]:
    payload: dict[str, object] = {"kind": analysis.suggested_distribution.value}
    if analysis.suggested_distribution == AccessDistribution.ZIPF and analysis.zipf_theta_estimate is not None:
        payload["zipf_theta"] = analysis.zipf_theta_estimate
    elif analysis.suggested_distribution == AccessDistribution.HOTSPOT:
        payload["hotspot_fraction"] = 0.10
        payload["hotspot_probability"] = 0.80
    return payload


def _draft_for_window(
    source_document,
    *,
    query_index: int,
    keys: list[int],
):
    if query_index >= len(source_document.resolved_spec.queries):
        raise ValueError(f"query_index {query_index} is outside the workload query range")

    analysis = analyze_access_trace(keys)
    raw_document = deepcopy(source_document.raw_document)
    raw_queries = raw_document.get("queries")
    if not isinstance(raw_queries, list) or query_index >= len(raw_queries):
        raise ValueError("raw workload query structure is unavailable")
    raw_query = raw_queries[query_index]
    if not isinstance(raw_query, dict):
        raise ValueError("selected raw workload query is not an object")

    raw_query["distribution"] = _distribution_payload(analysis)
    draft_text = yaml.safe_dump(
        raw_document,
        sort_keys=False,
        allow_unicode=False,
        default_flow_style=False,
    )
    try:
        draft_document = parse_workload_document(draft_text)
    except SpecParseError as exc:
        raise ValueError(f"trace-derived workload draft failed validation: {exc}") from exc
    return analysis, draft_document, draft_text


def _route_primitive(report: dict[str, Any], query_index: int) -> str | None:
    recommendation = report.get("recommendation")
    if not isinstance(recommendation, dict):
        return None
    routes = recommendation.get("routes")
    if not isinstance(routes, list):
        return None
    for route in routes:
        if isinstance(route, dict) and route.get("query_index") == query_index:
            primitive = route.get("primitive")
            return str(primitive) if primitive else None
    return None


def watch_hot_path(
    spec_text: str,
    *,
    current_structure: str,
    query_index: int,
    baseline_keys: list[int],
    observed_keys: list[int],
    threshold: float = 0.20,
    strategy: SearchStrategy = SearchStrategy.AUTO,
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
    beam_width: int = DEFAULT_BEAM_WIDTH,
) -> dict[str, Any]:
    """Re-evaluate one workload route when a fresh finite trace window arrives.

    Trace-derived distributions remain heuristic/user-review evidence. This
    function can recommend re-measurement/re-synthesis, but cannot mutate a
    persisted workload or authorize a runtime switch.
    """

    try:
        source_document = parse_workload_document(spec_text)
    except SpecParseError as exc:
        raise ValueError(str(exc)) from exc

    baseline_analysis, baseline_document, baseline_text = _draft_for_window(
        source_document,
        query_index=query_index,
        keys=baseline_keys,
    )
    observed_analysis, observed_document, observed_text = _draft_for_window(
        source_document,
        query_index=query_index,
        keys=observed_keys,
    )
    drift = compare_access_trace_windows(
        baseline_keys,
        observed_keys,
        threshold=threshold,
    )

    baseline_result = synthesize(
        baseline_document.resolved_spec,
        strategy=strategy,
        max_candidates=max_candidates,
        beam_width=beam_width,
    )
    observed_result = synthesize(
        observed_document.resolved_spec,
        strategy=strategy,
        max_candidates=max_candidates,
        beam_width=beam_width,
    )
    baseline_doctor = diagnose_hot_path(
        baseline_document.resolved_spec,
        baseline_result,
        current_structure=current_structure,
    )
    observed_doctor = diagnose_hot_path(
        observed_document.resolved_spec,
        observed_result,
        current_structure=current_structure,
    )

    baseline_winner = baseline_result.winner.id if baseline_result.winner else None
    observed_winner = observed_result.winner.id if observed_result.winner else None
    baseline_primitive = _route_primitive(baseline_doctor, query_index)
    observed_primitive = _route_primitive(observed_doctor, query_index)

    candidate_changed = baseline_winner != observed_winner
    route_changed = baseline_primitive != observed_primitive
    distribution_changed = (
        baseline_analysis.suggested_distribution
        != observed_analysis.suggested_distribution
    )

    if observed_result.winner is None:
        action = "BLOCKED_OBSERVED_WORKLOAD_INFEASIBLE"
        severity = "HIGH"
        rationale = "The observed trace-derived workload has no feasible candidate under the declared constraints."
    elif candidate_changed or route_changed:
        action = "RESYNTHESIZE_MEASURE_VERIFY_SHADOW"
        severity = "HIGH"
        rationale = (
            "The modeled winning design or the selected route primitive changed after applying the observed trace window."
        )
    elif drift.drifted or distribution_changed:
        action = "REMEASURE_RECOMMENDATION_AFTER_DRIFT"
        severity = "MEDIUM"
        rationale = (
            "The empirical access window changed materially, but the current modeled recommendation remained the same."
        )
    else:
        action = "KEEP_AND_MONITOR"
        severity = "LOW"
        rationale = (
            "The finite windows did not cross the configured drift threshold and the modeled recommendation stayed stable."
        )

    selected_query = observed_document.resolved_spec.queries[query_index]

    return {
        "schema": "morpheus-hot-path-watch-v1",
        "source_spec_hash": source_document.resolved_semantic_hash,
        "query_index": query_index,
        "query_kind": selected_query.kind.value,
        "query_field": selected_query.field,
        "current_structure": current_structure,
        "drift": drift.as_dict(),
        "baseline": {
            "analysis": baseline_analysis.as_dict(),
            "draft_spec_hash": baseline_document.resolved_semantic_hash,
            "draft_spec_text": baseline_text,
            "winner_candidate_id": baseline_winner,
            "route_primitive": baseline_primitive,
            "doctor": baseline_doctor,
        },
        "observed": {
            "analysis": observed_analysis.as_dict(),
            "draft_spec_hash": observed_document.resolved_semantic_hash,
            "draft_spec_text": observed_text,
            "winner_candidate_id": observed_winner,
            "route_primitive": observed_primitive,
            "doctor": observed_doctor,
        },
        "decision": {
            "action": action,
            "severity": severity,
            "rationale": rationale,
            "candidate_changed": candidate_changed,
            "route_primitive_changed": route_changed,
            "distribution_label_changed": distribution_changed,
            "recommended_next_gate": observed_doctor.get("next_gate") or observed_doctor.get("launch_state"),
        },
        "evidence_state": "FINITE_TRACE_DRIFT_REEVALUATED_MODEL_RECOMMENDATION_NOT_CONTROL_EVIDENCE",
        "eligible_for_runtime_automatic_control": False,
        "truth_boundary": (
            "Hot Path Watch compares only the supplied finite trace windows and re-runs MORPHEUS's modeled recommendation on trace-derived MWS drafts. "
            "Trace labels and drift thresholds are heuristic/research evidence, not calibrated online change-point guarantees. "
            "A changed or stable modeled recommendation is not a measured speedup claim. "
            "Any migration still requires explicit user review, target-machine measurement, generated-artifact verification, correctness/shadow comparison, and human-controlled deployment."
        ),
    }
