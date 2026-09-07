from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Event, Thread

import pytest

import app.process_transfer_protected_resource_fencing_durable as durable_module
from app.process_transfer_protected_resource_fencing import ProtectedResourceFencingDecision
from app.process_transfer_protected_resource_fencing_durable import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    DurableProtectedResourceFencingModel,
)


def _model(path: Path) -> DurableProtectedResourceFencingModel:
    return DurableProtectedResourceFencingModel(path, "resource-a", "fence-a")


def test_first_equal_newer_and_stale_semantics_survive_restart(tmp_path: Path) -> None:
    state_path = tmp_path / "fencing-state.json"
    first = _model(state_path)

    assert first.validate_fencing_token("resource-a", "fence-a", 41) == ProtectedResourceFencingDecision(
        "resource-a", "fence-a", 41, True
    )
    first_bytes = state_path.read_bytes()
    assert first.validate_fencing_token("resource-a", "fence-a", 41).accepted is True
    assert state_path.read_bytes() == first_bytes

    restarted = _model(state_path)
    state = restarted.snapshot()
    assert state is not None
    assert state.highest_accepted_fencing_counter == 41
    assert restarted.validate_fencing_token("resource-a", "fence-a", 40).accepted is False
    assert state_path.read_bytes() == first_bytes
    assert restarted.validate_fencing_token("resource-a", "fence-a", 42).accepted is True

    restarted_again = _model(state_path)
    assert restarted_again.snapshot().highest_accepted_fencing_counter == 42
    assert restarted_again.validate_fencing_token("resource-a", "fence-a", 41).accepted is False
    assert restarted_again.validate_fencing_token("resource-a", "fence-a", 42).accepted is True


def test_persisted_state_is_canonical_and_exactly_identity_bound(tmp_path: Path) -> None:
    state_path = tmp_path / "fencing-state.json"
    model = _model(state_path)
    model.validate_fencing_token("resource-a", "fence-a", 9)

    raw = state_path.read_bytes()
    assert raw.endswith(b"\n")
    payload = json.loads(raw)
    assert payload == {
        "fencing_authority_id": "fence-a",
        "highest_accepted_fencing_counter": 9,
        "resource_id": "resource-a",
        "version": 1,
    }
    assert raw == (
        b'{"fencing_authority_id":"fence-a","highest_accepted_fencing_counter":9,'
        b'"resource_id":"resource-a","version":1}\n'
    )


def test_corrupt_existing_state_fails_closed_at_restart(tmp_path: Path) -> None:
    state_path = tmp_path / "fencing-state.json"
    state_path.write_text("not-json", encoding="utf-8")

    with pytest.raises(ValueError, match="canonical JSON"):
        _model(state_path)
    assert state_path.read_text(encoding="utf-8") == "not-json"


def test_duplicate_json_keys_fail_closed_at_restart(tmp_path: Path) -> None:
    state_path = tmp_path / "fencing-state.json"
    state_path.write_text(
        '{"fencing_authority_id":"fence-a","highest_accepted_fencing_counter":9,'
        '"highest_accepted_fencing_counter":10,"resource_id":"resource-a","version":1}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="canonical JSON"):
        _model(state_path)


@pytest.mark.parametrize(
    "payload, message",
    [
        (
            {
                "fencing_authority_id": "fence-a",
                "highest_accepted_fencing_counter": 9,
                "resource_id": "resource-b",
                "version": 1,
            },
            "resource_id mismatch",
        ),
        (
            {
                "fencing_authority_id": "fence-b",
                "highest_accepted_fencing_counter": 9,
                "resource_id": "resource-a",
                "version": 1,
            },
            "fencing_authority_id mismatch",
        ),
    ],
)
def test_identity_drifted_persisted_state_is_rejected_before_use(tmp_path: Path, payload, message: str) -> None:
    state_path = tmp_path / "fencing-state.json"
    state_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    before = state_path.read_bytes()

    with pytest.raises(ValueError, match=message):
        _model(state_path)
    assert state_path.read_bytes() == before


def test_noncanonical_but_semantically_valid_json_is_rejected(tmp_path: Path) -> None:
    state_path = tmp_path / "fencing-state.json"
    state_path.write_text(
        json.dumps(
            {
                "version": 1,
                "resource_id": "resource-a",
                "highest_accepted_fencing_counter": 9,
                "fencing_authority_id": "fence-a",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="canonically encoded"):
        _model(state_path)


def test_external_tamper_after_construction_fails_before_new_token_is_accepted(tmp_path: Path) -> None:
    state_path = tmp_path / "fencing-state.json"
    model = _model(state_path)
    assert model.validate_fencing_token("resource-a", "fence-a", 10).accepted is True

    tampered = (
        b'{"fencing_authority_id":"fence-b","highest_accepted_fencing_counter":10,'
        b'"resource_id":"resource-a","version":1}\n'
    )
    state_path.write_bytes(tampered)

    with pytest.raises(ValueError, match="fencing_authority_id mismatch"):
        model.validate_fencing_token("resource-a", "fence-a", 11)
    assert state_path.read_bytes() == tampered


def test_replace_failure_preserves_previous_state_and_cleans_staging_file(tmp_path: Path, monkeypatch) -> None:
    state_path = tmp_path / "fencing-state.json"
    model = _model(state_path)
    assert model.validate_fencing_token("resource-a", "fence-a", 20).accepted is True
    previous = state_path.read_bytes()

    def fail_replace(src, dst) -> None:
        raise OSError("injected replace failure")

    monkeypatch.setattr(durable_module.os, "replace", fail_replace)
    with pytest.raises(OSError, match="injected replace failure"):
        model.validate_fencing_token("resource-a", "fence-a", 21)

    assert state_path.read_bytes() == previous
    assert list(tmp_path.glob(".fencing-state.json.*.tmp")) == []


def test_post_replace_reload_mismatch_fails_closed(tmp_path: Path, monkeypatch) -> None:
    state_path = tmp_path / "fencing-state.json"
    model = _model(state_path)
    assert model.validate_fencing_token("resource-a", "fence-a", 30).accepted is True
    real_replace = durable_module.os.replace

    def replace_then_tamper(src, dst) -> None:
        real_replace(src, dst)
        Path(dst).write_bytes(b"tampered-after-replace")

    monkeypatch.setattr(durable_module.os, "replace", replace_then_tamper)
    with pytest.raises(ValueError, match="bytes differ after replacement"):
        model.validate_fencing_token("resource-a", "fence-a", 31)
    assert state_path.read_bytes() == b"tampered-after-replace"


def test_request_identity_mismatch_fails_before_persisted_state_mutation(tmp_path: Path) -> None:
    state_path = tmp_path / "fencing-state.json"
    model = _model(state_path)
    model.validate_fencing_token("resource-a", "fence-a", 7)
    before = state_path.read_bytes()

    with pytest.raises(ValueError, match="resource_id does not match"):
        model.validate_fencing_token("resource-b", "fence-a", 100)
    with pytest.raises(ValueError, match="fencing_authority_id does not match"):
        model.validate_fencing_token("resource-a", "fence-b", 100)
    assert state_path.read_bytes() == before


def test_missing_parent_is_rejected_without_creating_storage(tmp_path: Path) -> None:
    state_path = tmp_path / "missing" / "fencing-state.json"
    with pytest.raises(FileNotFoundError, match="state parent does not exist"):
        _model(state_path)
    assert not state_path.parent.exists()


def test_durable_model_is_e11_callback_compatible(tmp_path: Path) -> None:
    model = _model(tmp_path / "fencing-state.json")
    decision = model.validate_fencing_token("resource-a", "fence-a", 55)
    assert isinstance(decision, ProtectedResourceFencingDecision)
    assert decision == ProtectedResourceFencingDecision("resource-a", "fence-a", 55, True)


def test_same_process_same_path_adapters_share_lock_identity(tmp_path: Path) -> None:
    state_path = tmp_path / "fencing-state.json"
    first = _model(state_path)
    second = _model(state_path)
    assert first._path_lock is second._path_lock


@pytest.mark.skipif(os.name == "nt", reason="file symlink creation is not reliably available on Windows CI")
def test_existing_file_symlink_uses_canonical_storage_identity(tmp_path: Path) -> None:
    state_path = tmp_path / "fencing-state.json"
    seed = _model(state_path)
    assert seed.validate_fencing_token("resource-a", "fence-a", 4).accepted is True

    alias_path = tmp_path / "fencing-state-alias.json"
    alias_path.symlink_to(state_path)
    through_alias = _model(alias_path)
    direct = _model(state_path)

    assert through_alias._path_lock is direct._path_lock
    assert through_alias._state_path == state_path.resolve(strict=False)
    assert through_alias.validate_fencing_token("resource-a", "fence-a", 5).accepted is True
    assert alias_path.is_symlink()
    assert direct.snapshot().highest_accepted_fencing_counter == 5


def test_same_process_same_path_adapters_serialize_full_transition(tmp_path: Path, monkeypatch) -> None:
    state_path = tmp_path / "fencing-state.json"
    first = _model(state_path)
    second = _model(state_path)
    first.validate_fencing_token("resource-a", "fence-a", 10)

    entered_replace = Event()
    release_replace = Event()
    second_done = Event()
    real_replace = durable_module.os.replace

    def blocking_replace(src, dst) -> None:
        if not entered_replace.is_set():
            entered_replace.set()
            assert release_replace.wait(timeout=5)
        real_replace(src, dst)

    monkeypatch.setattr(durable_module.os, "replace", blocking_replace)
    outcomes: list[ProtectedResourceFencingDecision] = []
    errors: list[BaseException] = []

    def run_first() -> None:
        try:
            outcomes.append(first.validate_fencing_token("resource-a", "fence-a", 11))
        except BaseException as exc:
            errors.append(exc)

    def run_second() -> None:
        try:
            outcomes.append(second.validate_fencing_token("resource-a", "fence-a", 12))
        except BaseException as exc:
            errors.append(exc)
        finally:
            second_done.set()

    first_thread = Thread(target=run_first)
    first_thread.start()
    assert entered_replace.wait(timeout=5)

    second_thread = Thread(target=run_second)
    second_thread.start()
    assert second_done.wait(timeout=0.1) is False

    release_replace.set()
    first_thread.join(timeout=5)
    second_thread.join(timeout=5)

    assert errors == []
    assert sorted((decision.fencing_counter, decision.accepted) for decision in outcomes) == [(11, True), (12, True)]
    assert _model(state_path).snapshot().highest_accepted_fencing_counter == 12


def test_different_paths_do_not_share_process_lock(tmp_path: Path) -> None:
    first = _model(tmp_path / "first.json")
    second = _model(tmp_path / "second.json")
    assert first._path_lock is not second._path_lock


def test_durable_model_never_grants_activation_or_traffic_authority(tmp_path: Path) -> None:
    model = _model(tmp_path / "fencing-state.json")
    assert model.automatic_control_allowed is False
    assert model.activation_allowed is False
    assert model.traffic_switching_allowed is False
    assert EVIDENCE_STATE == "LOCAL_DURABLE_PROTECTED_RESOURCE_FENCING_STATE_WITH_SHARED_PROCESS_PATH_LOCK_AND_PRE_REPLACE_CONFLICT_DETECTION_NO_DISTRIBUTED_ATTESTATION"


def test_truth_boundary_denies_distributed_and_scientific_claims() -> None:
    lowered = TRUTH_BOUNDARY.lower()
    assert "local filesystem-backed engineering adapter" in lowered
    assert "process-local" in lowered
    assert "does not establish cross-process locking" in lowered
    assert "another process or external writer can still race" in lowered
    assert "power-loss durability" in lowered
    assert "external-resource enforcement" in lowered
    assert "no benchmark" in lowered
    assert "production-readiness claim" in lowered
