from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CopilotResponse:
    answer: str
    mode: str
    confidence: str
    evidence_refs: list[str]
    limitations: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "mode": self.mode,
            "confidence": self.confidence,
            "evidence_refs": self.evidence_refs,
            "limitations": self.limitations,
        }


def _winner_summary(result: dict[str, Any]) -> str:
    winner = result.get("winner")
    if not winner:
        return "No feasible winner exists in this synthesis run."
    primitives = ", ".join(winner.get("unique_primitives", [])) or "none"
    return (
        f"Candidate {winner['id']} was selected with physical structures [{primitives}]. "
        f"Its modeled aggregate latency is {winner['predicted_latency_us']} us, modeled memory is "
        f"{winner['predicted_memory_mb']} MB, modeled build time is {winner['predicted_build_ms']} ms, "
        f"and its objective score is {winner['score']}. Prediction source: {winner.get('prediction_source', 'unknown')}."
    )


def answer_from_run(run: dict[str, Any], question: str) -> CopilotResponse:
    """Evidence-grounded deterministic copilot.

    This deliberately does not call an LLM. It maps common engineering questions
    to persisted experiment fields so explanations cannot outrun evidence. A
    future LLM may improve language or translate user intent, but the structured
    run record remains authoritative and unsupported claims remain prohibited.
    """

    query = question.strip().lower()
    if not query:
        raise ValueError("question cannot be empty")

    result = run["result"]
    winner = result.get("winner")
    run_id = run["run_id"]
    spec_hash = run["spec_hash"]
    evidence_refs = [f"run:{run_id}", f"spec:{spec_hash}"]
    if winner:
        evidence_refs.append(f"candidate:{winner['id']}")

    limitations = [
        "This response is generated only from persisted MORPHEUS run evidence.",
        "Modeled or calibrated predictions are not equivalent to end-to-end benchmark measurements.",
    ]

    if any(token in query for token in ("why", "choose", "selected", "winner")):
        if not winner:
            reasons: list[str] = []
            for candidate in result.get("candidates", [])[:8]:
                reasons.extend(candidate.get("rejection_reasons", []))
            reason_text = "; ".join(dict.fromkeys(reasons)) or "the evaluated candidates did not satisfy the hard gates"
            answer = f"MORPHEUS did not select a design because {reason_text}. Hard constraints were not silently relaxed."
        else:
            assignments = winner.get("assignments", [])
            routing = "; ".join(
                f"query {item['query_index']} {item['query_kind']}"
                + (f" on {item['field']}" if item.get("field") else "")
                + f" -> {item['primitive']}"
                for item in assignments
            )
            search = result.get("search_summary") or {}
            answer = (
                f"{_winner_summary(result)} It was the lowest-score feasible finalist under the declared objective and hard constraints. "
                f"Search strategy was {search.get('strategy', 'unknown')} and evaluated {search.get('evaluated_configurations', 'unknown')} "
                f"of {search.get('theoretical_configurations', 'unknown')} theoretical configurations. Routing: {routing}."
            )
        return CopilotResponse(answer, "DETERMINISTIC_EVIDENCE", "HIGH", evidence_refs, limitations)

    if any(token in query for token in ("measure", "benchmark", "real speed", "evidence", "confidence")):
        state = result.get("evidence_state", "unknown")
        profile = result.get("active_calibration_profile")
        if profile:
            answer = (
                f"This run's evidence state is {state}. Calibration profile {profile} was active, so supported primitive operations may be "
                "anchored to target-machine measurements, but the selected composite itself is still a prediction until generated code is "
                "benchmarked end-to-end under the same workload and machine protocol."
            )
        else:
            answer = (
                f"This run's evidence state is {state}. No calibration profile was active, so performance numbers are bootstrap model predictions, "
                "not measurements. Use the C++ calibration/benchmark pipeline before making quantitative performance claims."
            )
        return CopilotResponse(answer, "DETERMINISTIC_EVIDENCE", "HIGH", evidence_refs, limitations)

    if any(token in query for token in ("pareto", "alternative", "tradeoff", "trade-off")):
        front = result.get("pareto_front", [])
        if not front:
            answer = "This run has no feasible Pareto alternatives to compare."
        else:
            rows = []
            for candidate in front[:5]:
                rows.append(
                    f"{candidate['id']}: latency {candidate['predicted_latency_us']} us, memory {candidate['predicted_memory_mb']} MB, "
                    f"update {candidate['predicted_update_us']} us, build {candidate['predicted_build_ms']} ms"
                )
            answer = "The leading non-dominated alternatives are: " + " | ".join(rows) + "."
        return CopilotResponse(answer, "DETERMINISTIC_EVIDENCE", "HIGH", evidence_refs, limitations)

    if any(token in query for token in ("correct", "verify", "safe", "compile")):
        answer = (
            "Synthesis selection alone does not prove generated-code correctness. MORPHEUS requires the artifact path to generate standalone C++20, "
            "compile it with a pinned toolchain, run differential/stateful correctness tests against the logical reference model, and reject any "
            "mismatch before performance claims. This persisted synthesis run does not by itself prove all artifact gates executed."
        )
        limitations.append("Artifact verification evidence is not yet linked into each synthesis run record as a signed gate manifest.")
        return CopilotResponse(answer, "DETERMINISTIC_EVIDENCE", "HIGH", evidence_refs, limitations)

    if any(token in query for token in ("constraint", "memory", "latency limit", "build limit")):
        rejected = [candidate for candidate in result.get("candidates", []) if not candidate.get("feasible", False)]
        reasons: list[str] = []
        for candidate in rejected:
            reasons.extend(candidate.get("rejection_reasons", []))
        unique = list(dict.fromkeys(reasons))[:8]
        answer = (
            f"The run evaluated {len(result.get('candidates', []))} finalists and rejected {len(rejected)} on hard feasibility gates. "
            + ("Observed rejection reasons include: " + "; ".join(unique) + "." if unique else "No rejection reason was persisted for the finalist set.")
        )
        return CopilotResponse(answer, "DETERMINISTIC_EVIDENCE", "HIGH", evidence_refs, limitations)

    if any(token in query for token in ("runtime", "adapt", "drift", "switch")):
        answer = (
            "The runtime controller uses operation-mix drift, expected future benefit, switching cost, a safety multiplier and cooldown hysteresis. "
            "A recommendation becomes pending first; MORPHEUS requires explicit confirmation before control-plane active-candidate state changes. "
            "The current MVP still does not claim a real process-level hot swap."
        )
        return CopilotResponse(answer, "DETERMINISTIC_EVIDENCE", "HIGH", evidence_refs, limitations)

    answer = (
        f"{_winner_summary(result)} Evidence state: {result.get('evidence_state', 'unknown')}. "
        f"The run contains {len(result.get('candidates', []))} evaluated candidates and {len(result.get('pareto_front', []))} Pareto finalists. "
        "Ask why the design was selected, what was measured, which Pareto alternatives exist, what constraints rejected candidates, or how runtime adaptation is gated."
    )
    return CopilotResponse(answer, "DETERMINISTIC_EVIDENCE", "MEDIUM", evidence_refs, limitations)
