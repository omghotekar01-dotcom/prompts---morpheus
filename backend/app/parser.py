from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

import yaml
from pydantic import ValidationError

from .models import QueryKind, WorkloadSpec


class SpecParseError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedWorkloadDocument:
    """Raw/resolved MWS provenance boundary.

    `raw_document` represents the parsed user-authored object before Pydantic
    defaults/semantic resolution. `resolved_spec` is the validated compiler
    input. `raw_text_sha256` preserves exact submitted bytes while
    `resolved_semantic_hash` identifies canonical semantics. The two hashes are
    intentionally different concepts.
    """

    raw_document: dict[str, Any]
    resolved_spec: WorkloadSpec
    raw_text_sha256: str
    resolved_semantic_hash: str
    assumptions: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "raw_document": self.raw_document,
            "resolved_spec": canonical_dict(self.resolved_spec),
            "raw_text_sha256": self.raw_text_sha256,
            "resolved_semantic_hash": self.resolved_semantic_hash,
            "assumptions": list(self.assumptions),
            "evidence_state": "RAW_AND_RESOLVED_MWS_DISTINGUISHED",
        }


def _load_workload_object(raw: str, *, max_bytes: int) -> dict[str, Any]:
    if not raw.strip():
        raise SpecParseError("workload specification is empty")
    encoded = raw.encode("utf-8")
    if len(encoded) > max_bytes:
        raise SpecParseError(f"workload specification exceeds {max_bytes} bytes")

    try:
        loaded: Any = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise SpecParseError(f"invalid YAML/JSON: {exc}") from exc

    if not isinstance(loaded, dict):
        raise SpecParseError("top-level workload specification must be an object")
    return loaded


def _resolution_assumptions(spec: WorkloadSpec) -> tuple[str, ...]:
    assumptions: list[str] = []
    if "version" not in spec.model_fields_set:
        assumptions.append(f"version defaulted to {spec.version}")
    if "name" not in spec.model_fields_set:
        assumptions.append(f"name defaulted to {spec.name}")
    if "record_count" not in spec.model_fields_set:
        assumptions.append(f"record_count defaulted to {spec.record_count}")
    if "constraints" not in spec.model_fields_set:
        assumptions.append("constraints block resolved from defaults")
    if "objective" not in spec.model_fields_set:
        assumptions.append("objective block resolved from defaults")
    for index, query in enumerate(spec.queries):
        if "weight" not in query.model_fields_set:
            assumptions.append(f"query[{index}].weight defaulted to {query.weight}")
        if query.kind in {QueryKind.RANGE_SCAN, QueryKind.FILTER} and "selectivity" not in query.model_fields_set:
            assumptions.append(f"query[{index}].selectivity defaulted to {query.selectivity}")
    return tuple(assumptions)


def parse_workload_document(raw: str, *, max_bytes: int = 256_000) -> ParsedWorkloadDocument:
    loaded = _load_workload_object(raw, max_bytes=max_bytes)
    try:
        spec = WorkloadSpec.model_validate(loaded)
    except ValidationError as exc:
        raise SpecParseError(exc.json()) from exc
    except ValueError as exc:
        raise SpecParseError(str(exc)) from exc

    return ParsedWorkloadDocument(
        raw_document=json.loads(json.dumps(loaded, sort_keys=True, default=str)),
        resolved_spec=spec,
        raw_text_sha256=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        resolved_semantic_hash=semantic_hash(spec),
        assumptions=_resolution_assumptions(spec),
    )


def parse_workload_text(raw: str, *, max_bytes: int = 256_000) -> WorkloadSpec:
    return parse_workload_document(raw, max_bytes=max_bytes).resolved_spec


def canonical_dict(spec: WorkloadSpec) -> dict[str, Any]:
    return spec.model_dump(mode="json", exclude_none=True)


def canonical_json(spec: WorkloadSpec) -> str:
    return json.dumps(canonical_dict(spec), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def semantic_hash(spec: WorkloadSpec) -> str:
    return hashlib.sha256(canonical_json(spec).encode("utf-8")).hexdigest()
