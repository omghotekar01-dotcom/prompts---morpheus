from __future__ import annotations

import hashlib
import json
from typing import Any


SCHEMA = "morpheus-startup-pilot-capabilities-v1"


def _sha256(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def pilot_capabilities_payload() -> dict[str, Any]:
    """Return the startup/pilot capability ledger without widening MORPHEUS scope.

    This ledger is deliberately separate from the original 39/39 repository
    engineering score. It describes the extension track that makes the existing
    control plane safer to operate as a bounded single-node pilot.
    """

    core = {
        "schema": SCHEMA,
        "declared_scope": "SINGLE_NODE_ENGINEERING_PILOT",
        "production_deployment_authorized": False,
        "capabilities": {
            "fail_closed_pilot_readiness": "IMPLEMENTED_TESTED_LOCAL_PREFLIGHT",
            "guarded_single_worker_pilot_launcher": "IMPLEMENTED_TESTED_PREFLIGHT_ENFORCED_LOOPBACK_DEFAULT",
            "bounded_operational_observability": "IMPLEMENTED_TESTED_PROCESS_LOCAL_NO_BODY_OR_SECRET_CAPTURE",
            "durable_idempotent_pilot_synthesis": "IMPLEMENTED_TESTED_SQLITE_SINGLE_NODE_NOT_DISTRIBUTED_EXACTLY_ONCE",
            "manual_idempotency_resolution": "IMPLEMENTED_TESTED_OPERATOR_AUDITED_FAIL_CLOSED",
            "single_node_backup_restore": "IMPLEMENTED_TESTED_QUIESCENT_CONTENT_HASHED_ISOLATED_RESTORE",
            "pilot_browser_boundary": "IMPLEMENTED_TESTED_EXPLICIT_ORIGIN_HEADER_METHOD_POLICY",
            "retry_evidence_construction": "IMPLEMENTED_TESTED_OFFLINE_PROVENANCE_AND_SINGLE_USE_FENCES",
            "retry_execution_history_verification": "IMPLEMENTED_TESTED_OFFLINE_LINEAGE_AND_TERMINAL_STATE_VALIDATION",
            "automatic_retry_execution_authority": "NOT_GRANTED_BY_EVIDENCE_UTILITIES",
            "native_cross_process_hot_swap": "BLOCKED_NOT_IMPLEMENTED",
            "high_availability_storage": "NOT_IMPLEMENTED_SINGLE_NODE_SQLITE_AND_LOCAL_CAS",
            "multi_tenant_identity_and_authorization": "NOT_IMPLEMENTED_API_KEY_GUARD_ONLY",
        },
        "operator_surfaces": {
            "pilot_preflight": "CLI_AND_READ_ONLY_API",
            "guarded_pilot_start": "CLI_PREFLIGHT_REQUIRED_SINGLE_WORKER",
            "idempotency_health": "AGGREGATE_READ_ONLY_API",
            "backup_restore": "CLI_ONLY_NO_REMOTE_RESTORE_ENDPOINT",
            "ambiguity_resolution": "CLI_ONLY_MANUAL_EVIDENCE_AUDITED",
        },
        "truth_boundaries": [
            "Startup pilot capability does not imply external production validation, an SLA, a security certification, or customer traction.",
            "SQLite, local content-addressed artifacts, process-local telemetry and process-local rate limiting remain a single-node deployment model.",
            "The guarded launcher fixes one application worker and defaults to loopback; explicit non-loopback binding does not add TLS, identity, gateway/WAF, tenancy or production authorization.",
            "Retry authorization, execution-fence and evidence-chain utilities validate evidence; they do not themselves execute or authorize an automatic retry against a live external system.",
            "Generated-artifact and migration claims remain limited to their existing compile, correctness, same-process and evidence gates; native cross-process hot swap remains blocked.",
            "Performance, publication, novelty, patentability and universal superiority claims require their separate measured or external evidence programs.",
        ],
    }
    return {**core, "sha256": _sha256(core)}
