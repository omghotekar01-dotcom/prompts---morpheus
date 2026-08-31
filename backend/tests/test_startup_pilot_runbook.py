from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNBOOK = REPO_ROOT / "docs" / "STARTUP-PILOT-RUNBOOK.md"


def test_startup_pilot_runbook_covers_fail_closed_operator_workflow() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    required = (
        "python scripts/check_pilot_readiness.py",
        "POST /api/v2/pilot/synthesize",
        "GET /api/v2/system/operational-metrics",
        "python scripts/resolve_pilot_idempotency.py list",
        "CONFIRMED_NO_SIDE_EFFECT",
        "CONFIRMED_SIDE_EFFECT_PRESENT",
        "python scripts/manage_pilot_backup.py create",
        "python scripts/manage_pilot_backup.py verify",
        "python scripts/manage_pilot_backup.py restore",
        "production_deployment_authorized",
    )
    for marker in required:
        assert marker in text

    lowered = text.lower()
    assert "not a distributed exactly-once transaction" in lowered
    assert "local recovery checkpoint" in lowered
    assert "continuous replication" in lowered
    assert "do not themselves grant automatic live retry authority" in lowered
    assert "native cross-process hot swap" in lowered
