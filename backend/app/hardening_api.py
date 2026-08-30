from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .calibration import CALIBRATIONS
from .calibration_coverage import audit_workload_distribution_coverage
from .feature_registry import evaluate_feature_activation, registry_payload
from .parser import SpecParseError, parse_workload_text
from .pilot_readiness import build_pilot_readiness


router = APIRouter(prefix="/api/v2/system", tags=["MORPHEUS hardening and upgrade contracts"])


class FeatureActivationRequest(BaseModel):
    features: list[str] = Field(min_length=1, max_length=64)
    automatic_control: bool = False


class WorkloadCalibrationCoverageRequest(BaseModel):
    profile_id: str = Field(min_length=1, max_length=128)
    spec_text: str = Field(min_length=1, max_length=256_000)
    primitive_names: list[str] | None = Field(default=None, max_length=64)


def canonical_openapi_contract(document: dict[str, Any]) -> dict[str, Any]:
    """Extract the route/operation contract while ignoring prose-only OpenAPI noise."""

    paths: dict[str, Any] = {}
    for path in sorted(document.get("paths", {})):
        operations = document["paths"][path]
        normalized_operations: dict[str, Any] = {}
        for method in sorted(operations):
            if method.lower() not in {"get", "post", "put", "patch", "delete", "options", "head"}:
                continue
            operation = operations[method]
            responses = operation.get("responses", {})
            normalized_operations[method.lower()] = {
                "operation_id": operation.get("operationId"),
                "request_body_required": bool(operation.get("requestBody", {}).get("required", False)),
                "response_codes": sorted(str(code) for code in responses),
            }
        if normalized_operations:
            paths[path] = normalized_operations
    return {
        "schema": "morpheus-openapi-route-contract-v1",
        "paths": paths,
    }


def openapi_contract_fingerprint(document: dict[str, Any]) -> tuple[dict[str, Any], str]:
    contract = canonical_openapi_contract(document)
    encoded = json.dumps(contract, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return contract, hashlib.sha256(encoded).hexdigest()


@router.get("/features")
def features() -> dict[str, object]:
    return registry_payload()


@router.post("/features/evaluate")
def evaluate_features(request: FeatureActivationRequest) -> dict[str, object]:
    try:
        return evaluate_feature_activation(
            request.features,
            automatic_control=request.automatic_control,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/calibration/coverage/workload")
def workload_calibration_coverage(request: WorkloadCalibrationCoverageRequest) -> dict[str, object]:
    """Report optimizer-usable calibration identity for one concrete workload.

    The endpoint is deliberately read-only. It does not activate a profile,
    mutate cost-model state, interpolate across scales, or promote evidence.
    """

    try:
        profile = CALIBRATIONS.get(request.profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        spec = parse_workload_text(request.spec_text)
        report = audit_workload_distribution_coverage(
            profile,
            spec,
            primitive_names=request.primitive_names,
        )
    except (SpecParseError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return report.as_dict()


@router.get("/pilot-readiness")
def pilot_readiness() -> dict[str, object]:
    """Return a fail-closed operational preflight for the declared single-node pilot scope."""

    return build_pilot_readiness()


@router.get("/schema-contract")
def schema_contract(request: Request) -> dict[str, object]:
    contract, fingerprint = openapi_contract_fingerprint(request.app.openapi())
    return {
        "schema": "morpheus-api-contract-fingerprint-v1",
        "sha256": fingerprint,
        "route_count": len(contract["paths"]),
        "contract": contract,
        "truth_boundary": (
            "The fingerprint detects route/method/operation/response-code contract changes. "
            "It is not a semantic compatibility proof for every JSON field."
        ),
    }
