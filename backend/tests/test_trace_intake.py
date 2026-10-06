from __future__ import annotations

import pytest

from app.trace_intake import TraceIntakeError, normalize_trace_content


def test_plain_integer_trace_normalizes_and_binds_identity() -> None:
    report = normalize_trace_content("1, 2, 2\n3 4")

    assert report["source_format"] == "text"
    assert report["keys"] == [1, 2, 2, 3, 4]
    assert report["sample_count"] == 5
    assert report["unique_key_count"] == 4
    assert report["rejected_count"] == 0
    assert len(report["input_sha256"]) == 64
    assert len(report["normalized_window_sha256"]) == 64
    assert report["eligible_for_runtime_automatic_control"] is False


def test_csv_known_key_header_is_selected_only_when_unambiguous() -> None:
    report = normalize_trace_content(
        "timestamp,key,latency_us\n1,42,8\n2,42,9\n3,7,10\n",
        format_hint="csv",
    )

    assert report["selected_key_field"] == "key"
    assert report["key_selection_reason"] == "unambiguous_known_csv_header"
    assert report["keys"] == [42, 42, 7]


def test_csv_explicit_key_field_supports_real_export_column_names() -> None:
    report = normalize_trace_content(
        "time,sku_hash,route\n1,101,read\n2,102,read\n",
        format_hint="csv",
        key_field="sku_hash",
    )

    assert report["selected_key_field"] == "sku_hash"
    assert report["key_selection_reason"] == "explicit_csv_header"
    assert report["keys"] == [101, 102]


def test_json_event_array_supports_dotted_key_path() -> None:
    report = normalize_trace_content(
        '{"events":[{"request":{"key":9}},{"request":{"key":9}},{"request":{"key":12}}]}',
        format_hint="json",
        key_field="request.key",
    )

    assert report["source_format"] == "json"
    assert report["selected_key_field"] == "request.key"
    assert report["keys"] == [9, 9, 12]


def test_json_scalar_keys_object_is_unambiguous() -> None:
    report = normalize_trace_content('{"keys":[5,6,7,8]}', format_hint="json")

    assert report["selected_key_field"] is None
    assert report["keys"] == [5, 6, 7, 8]


def test_ambiguous_object_fields_fail_closed() -> None:
    with pytest.raises(TraceIntakeError, match="multiple possible key fields"):
        normalize_trace_content(
            '[{"key":1,"id":10},{"key":2,"id":11}]',
            format_hint="json",
        )


def test_invalid_rows_fail_closed_by_default() -> None:
    with pytest.raises(TraceIntakeError, match="invalid key row"):
        normalize_trace_content(
            "key\n1\nnot-an-int\n2\n",
            format_hint="csv",
        )


def test_invalid_rows_can_be_dropped_only_with_explicit_opt_in() -> None:
    report = normalize_trace_content(
        "key\n1\nnot-an-int\n2\n",
        format_hint="csv",
        allow_invalid_rows=True,
    )

    assert report["keys"] == [1, 2]
    assert report["rejected_count"] == 1
    assert report["rejected_samples"][0]["location"] == "row[3].key"
    assert "explicitly" in report["truth_boundary"]


def test_auto_detection_handles_json_and_multirow_csv() -> None:
    json_report = normalize_trace_content("[1,2,3]")
    csv_report = normalize_trace_content("key,op\n1,read\n2,read\n")

    assert json_report["source_format"] == "json"
    assert csv_report["source_format"] == "csv"


def test_hash_changes_when_normalized_window_changes() -> None:
    first = normalize_trace_content("1,2,3")
    second = normalize_trace_content("1,2,4")

    assert first["normalized_window_sha256"] != second["normalized_window_sha256"]


def test_single_invalid_or_too_short_trace_never_becomes_watch_evidence() -> None:
    with pytest.raises(TraceIntakeError, match="at least two"):
        normalize_trace_content("42")
