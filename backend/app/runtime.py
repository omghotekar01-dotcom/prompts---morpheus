from __future__ import annotations

from .models import AdaptationDecision, ObservedWorkloadSnapshot


def decide_adaptation(
    snapshot: ObservedWorkloadSnapshot,
    *,
    current_predicted_latency_us: float,
    alternative_predicted_latency_us: float,
    estimated_switching_cost_us: float,
    lambda_factor: float = 1.5,
    safety_margin_ratio: float = 0.10,
) -> AdaptationDecision:
    per_query_gain = max(current_predicted_latency_us - alternative_predicted_latency_us, 0.0)
    benefit = per_query_gain * snapshot.expected_future_queries
    threshold = lambda_factor * estimated_switching_cost_us * (1.0 + safety_margin_ratio)

    if benefit > threshold and per_query_gain > 0:
        action = "SWITCH_RECOMMENDED"
        reason = (
            "Predicted cumulative benefit exceeds transition-cost threshold. "
            "This is a model recommendation, not a completed hot-swap."
        )
    else:
        action = "RETAIN_CURRENT"
        reason = "Predicted benefit does not safely repay the estimated switching cost."

    return AdaptationDecision(
        action=action,
        predicted_benefit_us=round(benefit, 6),
        estimated_switching_cost_us=round(estimated_switching_cost_us, 6),
        threshold_us=round(threshold, 6),
        reason=reason,
    )
