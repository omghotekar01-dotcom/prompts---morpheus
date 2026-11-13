from __future__ import annotations

import os
from pathlib import Path
import pytest

from app.models import WorkloadSpec
from app.native_capabilities_bridge import NativeCapabilityError, native_capability_result


def _workload():
    return WorkloadSpec.model_validate({
        "record_count": 1000,
        "fields": [{"name": "name", "type": "string", "cardinality": 100}],
        "queries": [{"kind": "prefix_search", "field": "name"}],
    })


def test_compatibility_mode_no_native_executable(monkeypatch):
    monkeypatch.setenv("MORPHEUS_CAPABILITY_BACKEND", "python")
    assert native_capability_result(_workload(), _workload().queries[0]) is None


def test_strict_native_refuses_missing_binary(monkeypatch):
    monkeypatch.setenv("MORPHEUS_CAPABILITY_BACKEND", "native")
    monkeypatch.setenv("MORPHEUS_CAPABILITY_EXECUTABLE", "/missing/morpheus_native_capabilities")
    with pytest.raises(NativeCapabilityError, match="missing"):
        native_capability_result(_workload(), _workload().queries[0])


def test_actual_compiled_registry(monkeypatch):
    binary = os.getenv("MORPHEUS_CAPABILITY_EXECUTABLE")
    if not binary or not Path(binary).is_file():
        pytest.skip("compile the native C++ capabilities executable")
    monkeypatch.setenv("MORPHEUS_CAPABILITY_BACKEND", "native")
    report = native_capability_result(_workload(), _workload().queries[0])
    assert report is not None
    assert report["radix_trie"] == "eligible"
    assert report["robin_hood_hash"] == "unsupported_operation"
