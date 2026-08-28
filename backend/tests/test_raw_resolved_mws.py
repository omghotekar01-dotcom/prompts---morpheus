from __future__ import annotations

from app.parser import parse_workload_document, parse_workload_text, semantic_hash


RAW = """
fields:
  - name: id
    type: uint64
queries:
  - kind: range_scan
    field: id
""".strip()


def test_raw_and_resolved_mws_are_explicitly_distinct() -> None:
    document = parse_workload_document(RAW)
    assert "version" not in document.raw_document
    assert "record_count" not in document.raw_document
    assert "constraints" not in document.raw_document
    assert "objective" not in document.raw_document
    assert "selectivity" not in document.raw_document["queries"][0]

    resolved = document.resolved_spec
    assert resolved.version == "mws-0.1"
    assert resolved.record_count == 100_000
    assert resolved.queries[0].selectivity == 0.05
    assert document.resolved_semantic_hash == semantic_hash(resolved)
    assert len(document.raw_text_sha256) == 64
    assert document.raw_text_sha256 != document.resolved_semantic_hash
    assert "version defaulted to mws-0.1" in document.assumptions
    assert "record_count defaulted to 100000" in document.assumptions
    assert "constraints block resolved from defaults" in document.assumptions
    assert "objective block resolved from defaults" in document.assumptions
    assert "query[0].weight defaulted to 1.0" in document.assumptions
    assert "query[0].selectivity defaulted to 0.05" in document.assumptions

    # Legacy parser API intentionally remains the resolved-spec convenience path.
    assert parse_workload_text(RAW) == resolved


def test_raw_hash_changes_with_formatting_while_semantic_hash_does_not() -> None:
    compact = '{"fields":[{"name":"id","type":"uint64"}],"queries":[{"kind":"range_scan","field":"id"}]}'
    first = parse_workload_document(RAW)
    second = parse_workload_document(compact)
    assert first.raw_text_sha256 != second.raw_text_sha256
    assert first.resolved_semantic_hash == second.resolved_semantic_hash
