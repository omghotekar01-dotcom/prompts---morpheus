from __future__ import annotations

from copy import deepcopy

from app.idempotency import IdempotencyJournal
from app.pilot_readiness import build_pilot_readiness
from app.pilot_readiness_verifier import verify_pilot_readiness
from app.storage import StateStore
from app.toolchain import Toolchain


def _report(tmp_path):
    store = StateStore(db_path=tmp_path / "state.db", artifact_root=tmp_path / "artifacts")
    journal = IdempotencyJournal(tmp_path / "idempotency.db")
    try:
        return build_pilot_readiness(
            store=store,
            journal=journal,
            environment={
                "MORPHEUS_API_KEY": "pilot-secret-with-more-than-24-chars",
                "MORPHEUS_RATE_LIMIT_PER_MINUTE": "60",
            },
            toolchain_fn=lambda: Toolchain(kind="gnu", executable="/opt/test/g++", version="g++ test 1"),
        )
    finally:
        journal.close()
        store._connection.close()


def test_readiness_receipt_verifies_when_untampered(tmp_path) -> None:
    report = _report(tmp_path)
    assert report["ready"] is True
    assert verify_pilot_readiness(report) is True


def test_readiness_receipt_rejects_digest_and_state_tampering(tmp_path) -> None:
    report = _report(tmp_path)

    bad_digest = deepcopy(report)
    bad_digest["readiness_sha256"] = "f" * 64
    assert verify_pilot_readiness(bad_digest) is False

    forged_state = deepcopy(report)
    forged_state["ready"] = False
    forged_state["state"] = "PILOT_NOT_READY"
    assert verify_pilot_readiness(forged_state) is False


def test_readiness_receipt_rejects_derived_list_and_duplicate_check_tampering(tmp_path) -> None:
    report = _report(tmp_path)

    forged_advisories = deepcopy(report)
    forged_advisories["advisories"] = []
    assert verify_pilot_readiness(forged_advisories) is False

    duplicate = deepcopy(report)
    duplicate["checks"].append(deepcopy(duplicate["checks"][0]))
    assert verify_pilot_readiness(duplicate) is False


def test_readiness_receipt_rejects_scope_and_boolean_alias_tampering(tmp_path) -> None:
    report = _report(tmp_path)

    widened_scope = deepcopy(report)
    widened_scope["scope"]["deployment_shape"] = "MULTI_NODE_PRODUCTION"
    assert verify_pilot_readiness(widened_scope) is False

    bool_alias = deepcopy(report)
    bool_alias["checks"][0]["passed"] = 1
    assert verify_pilot_readiness(bool_alias) is False
