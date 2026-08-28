from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "evaluate_adaptation_trace.py"


def test_adaptation_analysis_cli_emits_policy_regret_report(tmp_path: Path) -> None:
    input_path = tmp_path / "trace.json"
    output_path = tmp_path / "report.json"
    input_path.write_text(
        json.dumps(
            {
                "initial_candidate_id": "hash",
                "phases": [
                    {"phase_id": "point", "queries": 100, "per_query_cost": {"hash": 1.0, "tree": 3.0}},
                    {"phase_id": "short-range", "queries": 10, "per_query_cost": {"hash": 8.0, "tree": 2.0}},
                    {"phase_id": "long-range", "queries": 100, "per_query_cost": {"hash": 8.0, "tree": 2.0}},
                ],
                "transition_costs": [
                    {"from": "hash", "to": "tree", "cost": 100.0},
                    {"from": "tree", "to": "hash", "cost": 100.0},
                ],
            }
        ),
        encoding="utf-8",
    )

    process = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(input_path),
            "--lambda-factor",
            "1",
            "--safety-margin-ratio",
            "0",
            "--output",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert process.returncode == 0, process.stderr
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["schema"] == "morpheus-adaptation-policy-report-v1"
    assert report["evidence_state"] == "ANALYSIS_OF_CALLER_SUPPLIED_COSTS_NOT_BENCHMARK_EVIDENCE"
    policies = {item["policy"]: item for item in report["policies"]}
    assert set(policies) == {"NEVER_SWITCH", "IMMEDIATE_SWITCH", "TRANSITION_AWARE", "OFFLINE_ORACLE"}
    assert policies["OFFLINE_ORACLE"]["regret_vs_offline_oracle"] == 0
    assert policies["TRANSITION_AWARE"]["cumulative_cost"] <= policies["NEVER_SWITCH"]["cumulative_cost"]
    assert policies["IMMEDIATE_SWITCH"]["transition_cost"] == 100.0
