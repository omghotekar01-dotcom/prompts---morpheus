from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping

from .idempotency import JOURNAL, IdempotencyJournal
from .storage import STORE, StateStore
from .toolchain import Toolchain, discover_toolchain


SCHEMA = "morpheus-pilot-readiness-v1"
_MIN_API_KEY_LENGTH = 24


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _check(check_id: str, *, required: bool, passed: bool, detail: str, evidence_state: str) -> dict[str, Any]:
    return {
        "id": check_id,
        "required": required,
        "passed": passed,
        "detail": detail,
        "evidence_state": evidence_state,
    }


def _rate_limit_configuration(environment: Mapping[str, str]) -> tuple[int, bool]:
    raw = str(environment.get("MORPHEUS_RATE_LIMIT_PER_MINUTE", "0")).strip()
    try:
        value = int(raw or "0")
    except ValueError:
        return 0, False
    return max(0, value), value >= 0


def build_pilot_readiness(
    *,
    store: StateStore = STORE,
    journal: IdempotencyJournal = JOURNAL,
    environment: Mapping[str, str] | None = None,
    toolchain_fn: Callable[[], Toolchain | None] = discover_toolchain,
    access_fn: Callable[[str | bytes | os.PathLike[str] | os.PathLike[bytes], int], bool] = os.access,
) -> dict[str, Any]:
    """Evaluate readiness for a guarded single-node MORPHEUS pilot.

    This is deliberately stricter than `/api/health`. It checks locally decidable
    operational prerequisites only and never upgrades MORPHEUS into a claim of
    HA, multi-tenant, hardened-sandbox or externally audited production readiness.
    """

    env = os.environ if environment is None else environment
    checks: list[dict[str, Any]] = []

    db_path = str(store.db_path)
    durable_db = db_path != ":memory:"
    if durable_db:
        resolved_db = Path(db_path).expanduser().resolve()
        db_parent = resolved_db.parent
        db_operable = db_parent.is_dir() and access_fn(db_parent, os.W_OK)
        db_detail = f"SQLite state is file-backed under {db_parent}." if db_operable else "SQLite state path is not writable."
    else:
        db_operable = False
        db_detail = "SQLite state is in-memory and will not survive process restart."
    checks.append(
        _check(
            "durable_state_store",
            required=True,
            passed=durable_db and db_operable,
            detail=db_detail,
            evidence_state="PILOT_STATE_STORE_DURABLE" if durable_db and db_operable else "PILOT_STATE_STORE_NOT_DURABLE",
        )
    )

    artifact_root = Path(store.artifact_root).expanduser().resolve()
    artifact_operable = artifact_root.is_dir() and access_fn(artifact_root, os.R_OK | os.W_OK)
    checks.append(
        _check(
            "content_addressed_artifact_store",
            required=True,
            passed=artifact_operable,
            detail=(
                f"Artifact root {artifact_root} is readable and writable."
                if artifact_operable
                else f"Artifact root {artifact_root} is not both readable and writable."
            ),
            evidence_state="PILOT_ARTIFACT_STORE_OPERABLE" if artifact_operable else "PILOT_ARTIFACT_STORE_UNAVAILABLE",
        )
    )

    try:
        ledger = store.verify_evidence_ledger()
        ledger_valid = ledger.get("valid") is True
        ledger_entries = int(ledger.get("entries", 0))
    except Exception:
        ledger_valid = False
        ledger_entries = 0
    checks.append(
        _check(
            "evidence_ledger_integrity",
            required=True,
            passed=ledger_valid,
            detail=(
                f"Evidence hash chain verified across {ledger_entries} entries."
                if ledger_valid
                else "Evidence hash chain verification failed or could not be completed."
            ),
            evidence_state="PILOT_EVIDENCE_LEDGER_VERIFIED" if ledger_valid else "PILOT_EVIDENCE_LEDGER_INVALID",
        )
    )

    try:
        journal_integrity = journal.verify_integrity()
        journal_ready = journal_integrity.get("valid") is True and journal_integrity.get("durable") is True
        ambiguous_count = int(journal_integrity.get("states", {}).get("AMBIGUOUS_FAILURE", 0))
    except Exception:
        journal_ready = False
        ambiguous_count = 0
    checks.append(
        _check(
            "durable_idempotency_journal",
            required=True,
            passed=journal_ready,
            detail=(
                f"Idempotency journal is durable and structurally valid; ambiguous records requiring investigation: {ambiguous_count}."
                if journal_ready
                else "Idempotency journal is unavailable, non-durable, or failed SQLite integrity checks."
            ),
            evidence_state="PILOT_IDEMPOTENCY_JOURNAL_READY" if journal_ready else "PILOT_IDEMPOTENCY_JOURNAL_NOT_READY",
        )
    )

    try:
        toolchain = toolchain_fn()
    except Exception:
        toolchain = None
    toolchain_ready = toolchain is not None and bool(toolchain.executable) and bool(toolchain.version)
    checks.append(
        _check(
            "native_cpp20_toolchain",
            required=True,
            passed=toolchain_ready,
            detail=(
                f"Native compiler available: {toolchain.kind} at {toolchain.executable}."
                if toolchain is not None
                else "No deterministic C++20 toolchain is available to verify generated artifacts."
            ),
            evidence_state="PILOT_NATIVE_TOOLCHAIN_AVAILABLE" if toolchain_ready else "PILOT_NATIVE_TOOLCHAIN_MISSING",
        )
    )

    api_key = str(env.get("MORPHEUS_API_KEY", ""))
    api_key_configured = bool(api_key)
    api_key_hygiene = api_key_configured and len(api_key) >= _MIN_API_KEY_LENGTH
    checks.append(
        _check(
            "api_key_guard",
            required=True,
            passed=api_key_hygiene,
            detail=(
                "API-key guard is configured and meets the pilot minimum length policy."
                if api_key_hygiene
                else "Set MORPHEUS_API_KEY to a non-empty secret of at least 24 characters before a pilot deployment."
            ),
            evidence_state="PILOT_API_KEY_GUARD_CONFIGURED" if api_key_hygiene else "PILOT_API_KEY_GUARD_INSUFFICIENT",
        )
    )

    rate_limit, rate_limit_valid = _rate_limit_configuration(env)
    rate_limit_ready = rate_limit_valid and rate_limit > 0
    checks.append(
        _check(
            "request_rate_limit",
            required=True,
            passed=rate_limit_ready,
            detail=(
                f"Process-local limiter configured at {rate_limit} requests/minute per identity."
                if rate_limit_ready
                else "Set MORPHEUS_RATE_LIMIT_PER_MINUTE to a positive integer before a pilot deployment."
            ),
            evidence_state="PILOT_RATE_LIMIT_CONFIGURED" if rate_limit_ready else "PILOT_RATE_LIMIT_DISABLED_OR_INVALID",
        )
    )

    try:
        summary = store.summary()
        active_calibration = summary.get("active_calibration_profile")
    except Exception:
        active_calibration = None
    checks.append(
        _check(
            "active_calibration_profile",
            required=False,
            passed=active_calibration is not None,
            detail=(
                f"Active calibration profile: {active_calibration}."
                if active_calibration is not None
                else "No active measured calibration profile; synthesis may use bootstrap/model priors."
            ),
            evidence_state=(
                "PILOT_ACTIVE_CALIBRATION_PRESENT"
                if active_calibration is not None
                else "PILOT_ACTIVE_CALIBRATION_ABSENT_ADVISORY"
            ),
        )
    )

    blockers = [item["id"] for item in checks if item["required"] and not item["passed"]]
    advisories = [item["id"] for item in checks if not item["required"] and not item["passed"]]
    ready = not blockers
    core = {
        "schema": SCHEMA,
        "ready": ready,
        "state": "PILOT_READY_SINGLE_NODE_SCOPE" if ready else "PILOT_NOT_READY",
        "checks": checks,
        "blockers": blockers,
        "advisories": advisories,
        "scope": {
            "deployment_shape": "SINGLE_NODE_LOCAL_CONTROL_PLANE",
            "process_local_rate_limit": True,
            "api_key_authentication_only": True,
            "durable_metadata": "SQLITE",
            "durable_idempotency": "SQLITE_SINGLE_NODE",
            "artifact_store": "LOCAL_CONTENT_ADDRESSED_FILESYSTEM",
        },
        "truth_boundaries": [
            "Pilot readiness is a local operational preflight, not a security certification or production SLA attestation.",
            "The API-key and rate-limit checks do not replace TLS termination, an external identity provider, a gateway/WAF, secret rotation or distributed abuse controls.",
            "SQLite, the local artifact store and the idempotency journal are appropriate only for the declared single-node pilot scope; no HA or multi-region durability is inferred.",
            "Idempotency PENDING/AMBIGUOUS states are never auto-expired because automatic recovery could duplicate an uncertain persisted side effect.",
            "Toolchain availability proves only that native verification can be attempted; generated artifacts still require their normal compile/correctness gates.",
            "An active calibration profile is advisory because bootstrap/model priors remain a supported evidence-labelled operating mode.",
        ],
    }
    return {**core, "readiness_sha256": _canonical_sha256(core)}
