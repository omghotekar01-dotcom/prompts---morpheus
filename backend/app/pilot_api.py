from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse

from .engine import DEFAULT_BEAM_WIDTH, DEFAULT_MAX_CANDIDATES, synthesize
from .idempotency import JOURNAL, request_sha256, validate_idempotency_key
from .models import SearchStrategy
from .parser import SpecParseError, parse_workload_text
from .storage import STORE


router = APIRouter(prefix="/api/v2/pilot", tags=["MORPHEUS single-node pilot contracts"])
_OPERATION = "pilot_synthesis_v1"


class PilotSynthesisRequest(BaseModel):
    spec_text: str = Field(min_length=1, max_length=256_000)
    strategy: SearchStrategy = SearchStrategy.AUTO
    max_candidates: int = Field(default=DEFAULT_MAX_CANDIDATES, ge=1, le=100_000)
    beam_width: int = Field(default=DEFAULT_BEAM_WIDTH, ge=1, le=4096)


def _response(status_code: int, payload: dict[str, Any], *, replayed: bool, key_sha256: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=payload,
        headers={
            "Idempotency-Replayed": "true" if replayed else "false",
            "X-Morpheus-Idempotency-Key-SHA256": key_sha256,
            "Cache-Control": "no-store",
        },
    )


@router.post("/synthesize")
def pilot_synthesize(
    request: PilotSynthesisRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
) -> JSONResponse:
    """Synthesize and persist one run behind a durable single-node idempotency reservation."""

    try:
        canonical_key = validate_idempotency_key(idempotency_key)
    except ValueError as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc)}, headers={"Cache-Control": "no-store"})

    request_document = {
        "schema": "morpheus-pilot-synthesis-request-v1",
        **request.model_dump(mode="json"),
    }
    digest = request_sha256(request_document)
    claim = JOURNAL.claim(operation=_OPERATION, key=canonical_key, request_digest=digest)

    if claim.disposition == "REPLAY":
        assert claim.response_status is not None and claim.response_payload is not None
        return _response(
            claim.response_status,
            claim.response_payload,
            replayed=True,
            key_sha256=claim.key_sha256,
        )
    if claim.disposition == "CONFLICT":
        return _response(
            409,
            {
                "detail": "Idempotency-Key was already used with a different pilot synthesis request",
                "evidence_state": "IDEMPOTENCY_KEY_REQUEST_CONFLICT",
            },
            replayed=False,
            key_sha256=claim.key_sha256,
        )
    if claim.disposition == "IN_PROGRESS":
        return _response(
            409,
            {
                "detail": "A pilot synthesis with this Idempotency-Key is already in progress",
                "evidence_state": "IDEMPOTENCY_REQUEST_IN_PROGRESS_FAIL_CLOSED",
            },
            replayed=False,
            key_sha256=claim.key_sha256,
        )
    if claim.disposition == "AMBIGUOUS":
        return _response(
            409,
            {
                "detail": "This Idempotency-Key has an ambiguous prior side-effect state and requires operator investigation",
                "evidence_state": "IDEMPOTENCY_AMBIGUOUS_FAILURE_REQUIRES_OPERATOR",
            },
            replayed=False,
            key_sha256=claim.key_sha256,
        )
    if claim.disposition == "RESOLVED_SIDE_EFFECT":
        return _response(
            409,
            {
                "detail": "Operator resolution confirmed that the prior request produced a side effect; this Idempotency-Key remains permanently blocked from automatic retry",
                "evidence_state": "IDEMPOTENCY_CONFIRMED_SIDE_EFFECT_PRESENT_RETRY_BLOCKED",
            },
            replayed=False,
            key_sha256=claim.key_sha256,
        )
    if claim.disposition != "NEW":
        return _response(
            500,
            {
                "detail": "Unknown idempotency disposition; request blocked fail-closed",
                "evidence_state": "IDEMPOTENCY_UNKNOWN_DISPOSITION_BLOCKED",
            },
            replayed=False,
            key_sha256=claim.key_sha256,
        )

    try:
        spec = parse_workload_text(request.spec_text)
        result = synthesize(
            spec,
            strategy=request.strategy,
            max_candidates=request.max_candidates,
            beam_width=request.beam_width,
        )
    except (SpecParseError, ValueError) as exc:
        payload = {"detail": str(exc), "evidence_state": "PILOT_SYNTHESIS_REQUEST_REJECTED"}
        JOURNAL.complete(
            operation=_OPERATION,
            key_sha256=claim.key_sha256,
            request_digest=digest,
            status_code=422,
            response_payload=payload,
        )
        return _response(422, payload, replayed=False, key_sha256=claim.key_sha256)
    except Exception:
        JOURNAL.release_pending_without_side_effect(
            operation=_OPERATION,
            key_sha256=claim.key_sha256,
            request_digest=digest,
        )
        return _response(
            500,
            {
                "detail": "Pilot synthesis failed before any persistence side effect",
                "evidence_state": "PILOT_SYNTHESIS_PRE_SIDE_EFFECT_FAILURE",
            },
            replayed=False,
            key_sha256=claim.key_sha256,
        )

    if result.winner is None:
        payload = {
            "detail": "no feasible configuration satisfies all hard constraints",
            "evidence_state": "PILOT_SYNTHESIS_NO_FEASIBLE_CONFIGURATION",
        }
        JOURNAL.complete(
            operation=_OPERATION,
            key_sha256=claim.key_sha256,
            request_digest=digest,
            status_code=409,
            response_payload=payload,
        )
        return _response(409, payload, replayed=False, key_sha256=claim.key_sha256)

    response_payload = result.model_dump(mode="json")
    try:
        run_id = STORE.save_synthesis(spec, request.spec_text, result)
    except Exception:
        JOURNAL.mark_ambiguous_failure(
            operation=_OPERATION,
            key_sha256=claim.key_sha256,
            request_digest=digest,
        )
        return _response(
            503,
            {
                "detail": "Pilot synthesis persistence failed after the idempotency reservation; automatic retry is blocked",
                "evidence_state": "PILOT_SYNTHESIS_AMBIGUOUS_SIDE_EFFECT_BLOCKED",
            },
            replayed=False,
            key_sha256=claim.key_sha256,
        )

    response_payload["run_id"] = run_id
    response_payload["pilot_contract"] = {
        "schema": "morpheus-pilot-synthesis-response-v1",
        "idempotency_request_sha256": digest,
        "idempotency_key_sha256": claim.key_sha256,
        "scope": "SINGLE_NODE_DURABLE_IDEMPOTENCY",
        "truth_boundary": (
            "This reservation prevents automatic duplicate persisted synthesis runs for the same key on the declared single-node journal. "
            "It is not a distributed exactly-once transaction across multiple MORPHEUS nodes."
        ),
    }
    try:
        JOURNAL.complete(
            operation=_OPERATION,
            key_sha256=claim.key_sha256,
            request_digest=digest,
            status_code=200,
            response_payload=response_payload,
        )
    except Exception:
        try:
            JOURNAL.mark_ambiguous_failure(
                operation=_OPERATION,
                key_sha256=claim.key_sha256,
                request_digest=digest,
            )
        except Exception:
            pass
        return _response(
            503,
            {
                "detail": "Synthesis was persisted but idempotency completion could not be certified; automatic retry is blocked",
                "evidence_state": "PILOT_SYNTHESIS_PERSISTED_IDEMPOTENCY_AMBIGUOUS",
            },
            replayed=False,
            key_sha256=claim.key_sha256,
        )

    return _response(200, response_payload, replayed=False, key_sha256=claim.key_sha256)
