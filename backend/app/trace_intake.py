from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass
from typing import Any, Iterable


SUPPORTED_FORMATS = {"auto", "text", "csv", "json"}
KNOWN_KEY_FIELDS = ("key", "id", "item_id", "record_id", "object_id", "entity_id")
MAX_KEYS = 100_000
MAX_CONTENT_BYTES = 2_000_000
MAX_REJECTED_SAMPLES = 20
JS_SAFE_INTEGER_MAX = 9_007_199_254_740_991


class TraceIntakeError(ValueError):
    pass


@dataclass(frozen=True)
class RejectedValue:
    location: str
    value: str
    reason: str

    def as_dict(self) -> dict[str, str]:
        return {
            "location": self.location,
            "value": self.value,
            "reason": self.reason,
        }


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _normalized_sha256(keys: Iterable[int]) -> str:
    payload = json.dumps(list(keys), separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return _sha256_bytes(payload)


def _bounded_content_bytes(content: str) -> bytes:
    raw = content.encode("utf-8")
    if not raw:
        raise TraceIntakeError("trace content is empty")
    if len(raw) > MAX_CONTENT_BYTES:
        raise TraceIntakeError(f"trace content exceeds the {MAX_CONTENT_BYTES} byte limit")
    return raw


def _coerce_integer(value: Any, *, location: str) -> tuple[int | None, RejectedValue | None]:
    if isinstance(value, bool):
        return None, RejectedValue(location, str(value), "boolean values are not integer keys")
    if isinstance(value, int):
        if abs(value) > JS_SAFE_INTEGER_MAX:
            return None, RejectedValue(location, str(value), "integer exceeds browser-safe range")
        return value, None
    if isinstance(value, float):
        if value.is_integer():
            parsed = int(value)
            if abs(parsed) > JS_SAFE_INTEGER_MAX:
                return None, RejectedValue(location, repr(value), "integer exceeds browser-safe range")
            return parsed, None
        return None, RejectedValue(location, repr(value), "non-integral numeric value")
    if isinstance(value, str):
        token = value.strip()
        if not token:
            return None, RejectedValue(location, value, "empty key value")
        if re.fullmatch(r"[+-]?\d+", token):
            try:
                parsed = int(token, 10)
            except ValueError:
                return None, RejectedValue(location, token, "integer conversion failed")
            if abs(parsed) > JS_SAFE_INTEGER_MAX:
                return None, RejectedValue(location, token[:200], "integer exceeds browser-safe range")
            return parsed, None
        return None, RejectedValue(location, token[:200], "value is not an integer")
    return None, RejectedValue(location, repr(value)[:200], f"unsupported key type: {type(value).__name__}")


def _extract_path(value: Any, path: str) -> tuple[Any, bool]:
    current = value
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None, False
        current = current[part]
    return current, True


def _select_object_key_field(rows: list[dict[str, Any]], requested: str | None) -> tuple[str, str]:
    if not rows:
        raise TraceIntakeError("trace contains no object rows")
    if requested:
        missing = [index for index, row in enumerate(rows) if not _extract_path(row, requested)[1]]
        if missing:
            raise TraceIntakeError(
                f"key_field {requested!r} is missing from object row {missing[0]}"
            )
        return requested, "explicit_key_field"

    present_everywhere = [
        field
        for field in KNOWN_KEY_FIELDS
        if all(_extract_path(row, field)[1] for row in rows)
    ]
    if len(present_everywhere) == 1:
        return present_everywhere[0], "unambiguous_known_field"
    if not present_everywhere:
        raise TraceIntakeError(
            "object trace needs key_field because no unambiguous known key column was found"
        )
    raise TraceIntakeError(
        "object trace has multiple possible key fields; set key_field explicitly: "
        + ", ".join(present_everywhere)
    )


def _parse_text(content: str) -> tuple[list[int], list[RejectedValue], str | None, str]:
    tokens = [item for item in re.split(r"[\s,;]+", content) if item.strip()]
    if not tokens:
        raise TraceIntakeError("text trace contains no key tokens")
    keys: list[int] = []
    rejected: list[RejectedValue] = []
    for index, token in enumerate(tokens):
        key, error = _coerce_integer(token, location=f"token[{index}]")
        if error is not None:
            rejected.append(error)
        elif key is not None:
            keys.append(key)
    return keys, rejected, None, "plain_integer_tokens"


def _csv_rows(content: str) -> tuple[list[list[str]], csv.Dialect]:
    try:
        dialect = csv.Sniffer().sniff(content[:8192], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(content), dialect)
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        raise TraceIntakeError("CSV trace contains no rows")
    return rows, dialect


def _parse_csv(
    content: str,
    *,
    key_field: str | None,
) -> tuple[list[int], list[RejectedValue], str | None, str]:
    rows, dialect = _csv_rows(content)

    if key_field:
        reader = csv.DictReader(io.StringIO(content), dialect=dialect)
        fieldnames = [name.strip() for name in (reader.fieldnames or []) if name is not None]
        if key_field not in fieldnames:
            raise TraceIntakeError(
                f"CSV key_field {key_field!r} is not in header: {', '.join(fieldnames) or '<none>'}"
            )
        keys: list[int] = []
        rejected: list[RejectedValue] = []
        for row_index, row in enumerate(reader, start=2):
            raw = row.get(key_field)
            key, error = _coerce_integer(raw, location=f"row[{row_index}].{key_field}")
            if error is not None:
                rejected.append(error)
            elif key is not None:
                keys.append(key)
        return keys, rejected, key_field, "explicit_csv_header"

    # A one-column CSV is unambiguous whether or not it contains a header.
    if all(len(row) == 1 for row in rows):
        start = 0
        selected_field: str | None = None
        first = rows[0][0].strip()
        if first.lower() in KNOWN_KEY_FIELDS:
            selected_field = first
            start = 1
        keys: list[int] = []
        rejected: list[RejectedValue] = []
        for row_index, row in enumerate(rows[start:], start=start + 1):
            key, error = _coerce_integer(row[0], location=f"row[{row_index}]")
            if error is not None:
                rejected.append(error)
            elif key is not None:
                keys.append(key)
        return keys, rejected, selected_field, "single_column_csv"

    header = [cell.strip() for cell in rows[0]]
    candidates = [name for name in KNOWN_KEY_FIELDS if name in header]
    if len(candidates) != 1:
        if not candidates:
            raise TraceIntakeError(
                "multi-column CSV needs key_field because no known key column was found"
            )
        raise TraceIntakeError(
            "multi-column CSV has multiple possible key fields; set key_field explicitly: "
            + ", ".join(candidates)
        )
    selected = candidates[0]
    index = header.index(selected)
    keys = []
    rejected = []
    for row_index, row in enumerate(rows[1:], start=2):
        raw = row[index] if index < len(row) else None
        key, error = _coerce_integer(raw, location=f"row[{row_index}].{selected}")
        if error is not None:
            rejected.append(error)
        elif key is not None:
            keys.append(key)
    return keys, rejected, selected, "unambiguous_known_csv_header"


def _json_event_rows(parsed: Any) -> tuple[list[Any], str]:
    if isinstance(parsed, list):
        return parsed, "json_array"
    if isinstance(parsed, dict):
        if isinstance(parsed.get("keys"), list):
            return parsed["keys"], "json_keys_array"
        if isinstance(parsed.get("events"), list):
            return parsed["events"], "json_events_array"
        if isinstance(parsed.get("records"), list):
            return parsed["records"], "json_records_array"
    raise TraceIntakeError(
        "JSON trace must be an array or an object containing keys, events, or records"
    )


def _parse_json(
    content: str,
    *,
    key_field: str | None,
) -> tuple[list[int], list[RejectedValue], str | None, str]:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise TraceIntakeError(f"invalid JSON trace: {exc.msg}") from exc

    rows, container_reason = _json_event_rows(parsed)
    if not rows:
        raise TraceIntakeError("JSON trace contains no rows")

    if all(not isinstance(row, dict) for row in rows):
        if key_field:
            raise TraceIntakeError("key_field cannot be used with a scalar JSON key array")
        keys: list[int] = []
        rejected: list[RejectedValue] = []
        for index, value in enumerate(rows):
            key, error = _coerce_integer(value, location=f"item[{index}]")
            if error is not None:
                rejected.append(error)
            elif key is not None:
                keys.append(key)
        return keys, rejected, None, container_reason

    if not all(isinstance(row, dict) for row in rows):
        raise TraceIntakeError("JSON trace cannot mix scalar keys and object events")

    object_rows = [row for row in rows if isinstance(row, dict)]
    selected, selection_reason = _select_object_key_field(object_rows, key_field)
    keys = []
    rejected = []
    for index, row in enumerate(object_rows):
        value, exists = _extract_path(row, selected)
        if not exists:
            rejected.append(RejectedValue(f"item[{index}].{selected}", "<missing>", "key field missing"))
            continue
        key, error = _coerce_integer(value, location=f"item[{index}].{selected}")
        if error is not None:
            rejected.append(error)
        elif key is not None:
            keys.append(key)
    return keys, rejected, selected, f"{container_reason}:{selection_reason}"


def _detect_format(content: str) -> tuple[str, str]:
    stripped = content.lstrip()
    if stripped.startswith("[") or stripped.startswith("{"):
        return "json", "leading_json_delimiter"

    # Preserve the product's existing integer-window UX. If every whitespace /
    # comma / semicolon token is already a valid integer key, it is plain trace
    # input even when commas or newlines are present.
    text_keys, text_rejected, _, _ = _parse_text(content)
    if len(text_keys) >= 2 and not text_rejected:
        return "text", "all_tokens_are_integer_keys"

    try:
        rows, _ = _csv_rows(content)
    except TraceIntakeError:
        return "text", "fallback_plain_text"
    if len(rows) > 1 or (rows and len(rows[0]) > 1):
        return "csv", "delimited_rows_detected"
    return "text", "fallback_plain_text"


def normalize_trace_content(
    content: str,
    *,
    format_hint: str = "auto",
    key_field: str | None = None,
    allow_invalid_rows: bool = False,
) -> dict[str, Any]:
    raw = _bounded_content_bytes(content)
    normalized_hint = format_hint.strip().lower()
    if normalized_hint not in SUPPORTED_FORMATS:
        raise TraceIntakeError(
            "format_hint must be one of: " + ", ".join(sorted(SUPPORTED_FORMATS))
        )

    source_format = normalized_hint
    detection_reason = "explicit_format"
    if normalized_hint == "auto":
        source_format, detection_reason = _detect_format(content)

    if source_format == "json":
        keys, rejected, selected_field, selection_reason = _parse_json(
            content,
            key_field=key_field,
        )
    elif source_format == "csv":
        keys, rejected, selected_field, selection_reason = _parse_csv(
            content,
            key_field=key_field,
        )
    else:
        if key_field:
            raise TraceIntakeError("key_field is only valid for CSV or JSON object traces")
        keys, rejected, selected_field, selection_reason = _parse_text(content)

    if len(keys) > MAX_KEYS:
        raise TraceIntakeError(f"normalized trace exceeds the {MAX_KEYS} key limit")
    if rejected and not allow_invalid_rows:
        first = rejected[0]
        raise TraceIntakeError(
            f"trace contains {len(rejected)} invalid key row(s); first rejection at "
            f"{first.location}: {first.reason}. Set allow_invalid_rows=true only after explicit review."
        )
    if len(keys) < 2:
        raise TraceIntakeError("normalized trace needs at least two valid integer keys")

    return {
        "schema": "morpheus-real-workload-trace-intake-v1",
        "source_format": source_format,
        "format_detection_reason": detection_reason,
        "selected_key_field": selected_field,
        "key_selection_reason": selection_reason,
        "sample_count": len(keys),
        "unique_key_count": len(set(keys)),
        "rejected_count": len(rejected),
        "rejected_samples": [item.as_dict() for item in rejected[:MAX_REJECTED_SAMPLES]],
        "input_sha256": _sha256_bytes(raw),
        "normalized_window_sha256": _normalized_sha256(keys),
        "keys": keys,
        "eligible_for_runtime_automatic_control": False,
        "truth_boundary": (
            "This adapter only normalizes the supplied bounded trace into integer keys. "
            "It does not prove that the window is representative, infer missing semantics, "
            "measure performance, mutate a workload, or authorize migration/runtime control. "
            "Ambiguous key columns and invalid rows fail closed unless the caller explicitly "
            "allows dropping invalid rows after review."
        ),
    }
