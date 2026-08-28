#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.adaptation_research import (  # noqa: E402
    AdaptationPhase,
    evaluate_immediate_switch,
    evaluate_never_switch,
    evaluate_offline_oracle,
    evaluate_transition_aware,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate MORPHEUS adaptation policies over caller-supplied phase and transition costs."
    )
    parser.add_argument("input", type=Path, help="JSON input containing phases, initial_candidate_id and transition_costs")
    parser.add_argument("--output", type=Path, default=None, help="Optional output JSON path; stdout is always emitted")
    parser.add_argument("--lambda-factor", type=float, default=1.5)
    parser.add_argument("--safety-margin-ratio", type=float, default=0.10)
    parser.add_argument("--cooldown-phases", type=int, default=0)
    return parser


def _transition_map(raw: object) -> dict[tuple[str, str], float]:
    if not isinstance(raw, list):
        raise ValueError("transition_costs must be a list of {from,to,cost} records")
    out: dict[tuple[str, str], float] = {}
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("transition_cost entries must be objects")
        source = str(item["from"])
        target = str(item["to"])
        key = (source, target)
        if key in out:
            raise ValueError(f"duplicate transition cost for {source!r} -> {target!r}")
        out[key] = float(item["cost"])
    return out


def _load(path: Path) -> tuple[str, list[AdaptationPhase], dict[tuple[str, str], float]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    initial = str(payload["initial_candidate_id"])
    raw_phases = payload["phases"]
    if not isinstance(raw_phases, list):
        raise ValueError("phases must be a list")
    phases = [
        AdaptationPhase(
            phase_id=str(item["phase_id"]),
            queries=int(item["queries"]),
            per_query_cost={str(key): float(value) for key, value in item["per_query_cost"].items()},
        )
        for item in raw_phases
    ]
    return initial, phases, _transition_map(payload.get("transition_costs", []))


def main() -> int:
    args = _parser().parse_args()
    try:
        initial, phases, transitions = _load(args.input)
        reports = [
            evaluate_never_switch(phases, initial_candidate_id=initial),
            evaluate_immediate_switch(phases, initial_candidate_id=initial, transition_costs=transitions),
            evaluate_transition_aware(
                phases,
                initial_candidate_id=initial,
                transition_costs=transitions,
                lambda_factor=args.lambda_factor,
                safety_margin_ratio=args.safety_margin_ratio,
                cooldown_phases=args.cooldown_phases,
            ),
            evaluate_offline_oracle(phases, initial_candidate_id=initial, transition_costs=transitions),
        ]
        oracle_cost = reports[-1].cumulative_cost
        result = {
            "schema": "morpheus-adaptation-policy-report-v1",
            "input": str(args.input),
            "parameters": {
                "lambda_factor": args.lambda_factor,
                "safety_margin_ratio": args.safety_margin_ratio,
                "cooldown_phases": args.cooldown_phases,
            },
            "policies": [
                {
                    **report.as_dict(),
                    "regret_vs_offline_oracle": report.cumulative_cost - oracle_cost,
                }
                for report in reports
            ],
            "evidence_state": "ANALYSIS_OF_CALLER_SUPPLIED_COSTS_NOT_BENCHMARK_EVIDENCE",
        }
        rendered = json.dumps(result, sort_keys=True, indent=2)
        print(rendered)
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered + "\n", encoding="utf-8")
        return 0
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"adaptation evaluation failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
