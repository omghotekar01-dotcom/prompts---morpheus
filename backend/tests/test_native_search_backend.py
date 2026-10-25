from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess

import pytest

from app import engine
from app.models import SearchStrategy
from app.native_search_backend import NativeSearchError, select_native_combinations
from app.parser import parse_workload_text


def _spec(record_count: int):
    return parse_workload_text(
        "name: dynamic_native_case\n"
        f"record_count: {record_count}\n"
        "fields:\n  - name: id\n    type: uint64\n"
        "queries:\n  - kind: point_lookup\n    field: id\n    weight: 1\n"
    )


def test_native_bridge_serializes_real_workload_and_validates_output(monkeypatch):
    import app.native_search_backend as bridge

    monkeypatch.setenv("MORPHEUS_SEARCH_BACKEND", "native")
    monkeypatch.setattr(bridge, "native_search_executable", lambda: Path("/test/morpheus_native_search"))
    inputs: list[str] = []

    def fake_run(command, **kwargs):
        assert command == ["/test/morpheus_native_search"]
        assert kwargs["timeout"] == 15
        inputs.append(kwargs["input"])
        return CompletedProcess(command, 0, "OK exhaustive 2\nC 0\nC 1\n", "")

    monkeypatch.setattr(bridge.subprocess, "run", fake_run)
    options = [["ordered_tree", "robin_hood_hash"]]
    first = select_native_combinations(
        _spec(100), options, strategy=SearchStrategy.AUTO,
        max_candidates=128, beam_width=16,
    )
    second = select_native_combinations(
        _spec(100000), options, strategy=SearchStrategy.AUTO,
        max_candidates=128, beam_width=16,
    )
    assert first == second == (
        SearchStrategy.EXHAUSTIVE, [("ordered_tree",), ("robin_hood_hash",)],
    )
    assert inputs[0] != inputs[1]  # Cost estimates and index memory vary with user data.
    assert inputs[0].startswith("MORPHEUS_NATIVE_SEARCH_V1\n")


def test_native_required_is_fail_closed(monkeypatch):
    import app.native_search_backend as bridge

    monkeypatch.setenv("MORPHEUS_SEARCH_BACKEND", "native")
    monkeypatch.setattr(bridge, "native_search_executable", lambda: None)
    with pytest.raises(NativeSearchError, match="required"):
        select_native_combinations(
            _spec(10), [["ordered_tree"]], strategy=SearchStrategy.AUTO,
            max_candidates=10, beam_width=2,
        )


def test_legacy_python_path_is_explicit(monkeypatch):
    import app.native_search_backend as bridge

    monkeypatch.setenv("MORPHEUS_SEARCH_BACKEND", "python")
    monkeypatch.setattr(bridge, "native_search_executable", lambda: None)
    assert select_native_combinations(
        _spec(10), [["ordered_tree"]], strategy=SearchStrategy.AUTO,
        max_candidates=10, beam_width=2,
    ) is None


@pytest.mark.parametrize(
    "bad_output",
    [
        "",
        "OK auto 1\nC 0\n",
        "OK exhaustive 2\nC 0\n",
        "OK exhaustive 2\nC 0\nC 0\n",
        "OK exhaustive 1\nC 99\n",
    ],
)
def test_native_protocol_errors_are_never_silently_accepted(monkeypatch, bad_output):
    import app.native_search_backend as bridge

    monkeypatch.setenv("MORPHEUS_SEARCH_BACKEND", "native")
    monkeypatch.setattr(bridge, "native_search_executable", lambda: Path("/test/morpheus_native_search"))
    monkeypatch.setattr(
        bridge.subprocess, "run",
        lambda *args, **kwargs: CompletedProcess(args[0], 0, bad_output, ""),
    )
    with pytest.raises(NativeSearchError):
        select_native_combinations(
            _spec(100), [["ordered_tree", "robin_hood_hash"]],
            strategy=SearchStrategy.AUTO, max_candidates=20, beam_width=4,
        )


def test_synthesis_uses_native_finalists_for_actual_candidate_evaluation(monkeypatch):
    def native(spec, options, **kwargs):
        assert spec.record_count == 4731
        assert kwargs["strategy"] == SearchStrategy.AUTO
        return SearchStrategy.GREEDY, [(options[0][0],)]

    monkeypatch.setattr(engine, "select_native_combinations", native)
    output = engine.synthesize(_spec(4731))
    assert output.winner is not None
    assert output.search_summary is not None
    assert output.search_summary.strategy == SearchStrategy.GREEDY
    assert output.search_summary.evaluated_configurations == 1
    assert output.winner.assignments[0].primitive == "ordered_tree"
    assert any("compiled C++20" in warning for warning in output.warnings)
