from __future__ import annotations

import hashlib
import json
from typing import Any

import yaml
from pydantic import ValidationError

from .models import WorkloadSpec


class SpecParseError(ValueError):
    pass


def parse_workload_text(raw: str, *, max_bytes: int = 256_000) -> WorkloadSpec:
    if not raw.strip():
        raise SpecParseError("workload specification is empty")
    if len(raw.encode("utf-8")) > max_bytes:
        raise SpecParseError(f"workload specification exceeds {max_bytes} bytes")

    try:
        loaded: Any = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise SpecParseError(f"invalid YAML/JSON: {exc}") from exc

    if not isinstance(loaded, dict):
        raise SpecParseError("top-level workload specification must be an object")

    try:
        return WorkloadSpec.model_validate(loaded)
    except ValidationError as exc:
        raise SpecParseError(exc.json()) from exc
    except ValueError as exc:
        raise SpecParseError(str(exc)) from exc


def canonical_dict(spec: WorkloadSpec) -> dict[str, Any]:
    return spec.model_dump(mode="json", exclude_none=True)


def canonical_json(spec: WorkloadSpec) -> str:
    return json.dumps(canonical_dict(spec), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def semantic_hash(spec: WorkloadSpec) -> str:
    return hashlib.sha256(canonical_json(spec).encode("utf-8")).hexdigest()
