from __future__ import annotations

from fastapi import APIRouter, Request

from .advanced_api import capabilities_v2_payload
from .feature_registry import registry_payload
from .hardening_api import openapi_contract_fingerprint
from .pilot_capabilities import pilot_capabilities_payload
from .pilot_readiness import build_pilot_readiness
from .startup_readiness import build_startup_mvp_readiness
from .startup_readiness_evidence import (
    build_startup_readiness_evidence,
    compare_startup_readiness_evidence_to_current,
)
from .toolchain import system_diagnostics


router = APIRouter(prefix="/api/v2/system", tags=["MORPHEUS startup-MVP readiness"])


def _current_startup_mvp_readiness(request: Request) -> dict[str, object]:
    contract, contract_sha256 = openapi_contract_fingerprint(request.app.openapi())
    return build_startup_mvp_readiness(
        capabilities=capabilities_v2_payload(),
        feature_registry=registry_payload(),
        pilot_readiness=build_pilot_readiness(),
        pilot_capabilities=pilot_capabilities_payload(),
        diagnostics=system_diagnostics(),
        api_contract_sha256=contract_sha256,
        api_route_count=len(contract["paths"]),
    )


@router.get("/startup-mvp-readiness")
def startup_mvp_readiness(request: Request) -> dict[str, object]:
    """Return the fail-closed local startup-MVP readiness contract.

    The result deliberately separates local single-user product readiness from
    guarded single-node pilot deployment configuration and from external
    production/commercial/scientific outcomes.
    """

    return _current_startup_mvp_readiness(request)


@router.get("/startup-mvp-readiness/evidence")
def startup_mvp_readiness_evidence(request: Request) -> dict[str, object]:
    """Return deterministic, replayable and explicitly non-authoritative readiness evidence."""

    return build_startup_readiness_evidence(_current_startup_mvp_readiness(request))


@router.get("/startup-mvp-readiness/evidence/current-coherence")
def startup_mvp_readiness_evidence_current_coherence(request: Request) -> dict[str, object]:
    """Report whether freshly replayed local evidence matches freshly composed readiness.

    This is a deterministic local coherence check, not freshness/authenticity,
    remote attestation, deployment authorization or an automatic-control grant.
    """

    current = _current_startup_mvp_readiness(request)
    evidence = build_startup_readiness_evidence(current)
    return compare_startup_readiness_evidence_to_current(evidence, current)
