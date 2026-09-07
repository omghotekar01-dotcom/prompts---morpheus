from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any

from .process_transfer_protected_resource_fencing import ProtectedResourceFencingDecision


EVIDENCE_STATE = "LOCAL_DURABLE_PROTECTED_RESOURCE_FENCING_STATE_NO_DISTRIBUTED_ATTESTATION"
TRUTH_BOUNDARY = (
    "This module is a local filesystem-backed engineering adapter for one exact protected-resource and fencing-authority identity "
    "pair. It re-reads and validates canonical persisted state before each token decision, persists a strictly newer accepted "
    "generation through same-directory temporary staging, file fsync, os.replace, and exact post-replace reload, and therefore "
    "supports tested fail-closed restart recovery within that narrow local-process/filesystem model. Equal generations are "
    "idempotent and lower generations are rejected without rewriting state. A live adapter that has already observed or persisted "
    "durable state also fails closed if that state later disappears; this does not detect deletion that happened before a fresh "
    "adapter was constructed. It does not establish cross-process locking or linearizability, distributed atomicity, consensus, "
    "lease semantics, power-loss durability, filesystem or storage-device correctness, availability, authentication, compromise "
    "resistance, external-resource enforcement, atomic cutover, live replacement, activation or traffic switching; and makes no "
    "benchmark, performance, novelty, scientific-effect, HA/SLA or production-readiness claim."
)

_STATE_VERSION = 1
_STATE_KEYS = {
    "fencing_authority_id",
    "highest_accepted_fencing_counter",
    "resource_id",
    "version",
}


@dataclass(frozen=True)
class DurableProtectedResourceFencingState:
    resource_id: str
    fencing_authority_id: str
    highest_accepted_fencing_counter: int


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


class DurableProtectedResourceFencingModel:
    """Local filesystem-backed stale-token reference adapter for one identity pair.

    The adapter serializes calls only between threads sharing this exact Python object. It intentionally does not claim that two
    processes or two independently constructed adapters pointing at the same path are mutually excluded.
    """

    def __init__(self, state_path: str | os.PathLike[str], resource_id: str, fencing_authority_id: str) -> None:
        self._resource_id = self._require_identity(resource_id, "resource_id")
        self._fencing_authority_id = self._require_identity(fencing_authority_id, "fencing_authority_id")
        self._state_path = Path(state_path)
        self._lock = RLock()
        self._state_was_established = False

        parent = self._state_path.parent
        if not parent.exists():
            raise FileNotFoundError(f"state parent does not exist: {parent}")
        if not parent.is_dir():
            raise NotADirectoryError(f"state parent is not a directory: {parent}")
        if self._state_path.exists() and not self._state_path.is_file():
            raise ValueError("state_path must refer to a regular file when it exists")

        # Fail closed at construction if existing persisted state is malformed or belongs to another identity.
        initial_state = self._load_state()
        self._state_was_established = initial_state is not None

    @staticmethod
    def _require_identity(value: str, field: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be a non-empty string")
        return value

    @staticmethod
    def _require_counter(value: int) -> int:
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError("fencing_counter must be a non-negative integer")
        return value

    def _canonical_bytes(self, counter: int) -> bytes:
        payload = {
            "fencing_authority_id": self._fencing_authority_id,
            "highest_accepted_fencing_counter": counter,
            "resource_id": self._resource_id,
            "version": _STATE_VERSION,
        }
        return (json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")

    def _decode_state(self, raw: bytes) -> DurableProtectedResourceFencingState:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("persisted fencing state is not valid UTF-8") from exc
        try:
            payload = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError("persisted fencing state is not valid canonical JSON") from exc
        if not isinstance(payload, dict) or set(payload) != _STATE_KEYS:
            raise ValueError("persisted fencing state has an unexpected schema")
        version = payload["version"]
        if not isinstance(version, int) or isinstance(version, bool) or version != _STATE_VERSION:
            raise ValueError("persisted fencing state version mismatch")
        resource_id = self._require_identity(payload["resource_id"], "resource_id")
        authority_id = self._require_identity(payload["fencing_authority_id"], "fencing_authority_id")
        counter = self._require_counter(payload["highest_accepted_fencing_counter"])
        if resource_id != self._resource_id:
            raise ValueError("persisted fencing state resource_id mismatch")
        if authority_id != self._fencing_authority_id:
            raise ValueError("persisted fencing state fencing_authority_id mismatch")
        if raw != self._canonical_bytes(counter):
            raise ValueError("persisted fencing state is not canonically encoded")
        return DurableProtectedResourceFencingState(resource_id, authority_id, counter)

    def _load_state(self) -> DurableProtectedResourceFencingState | None:
        try:
            raw = self._state_path.read_bytes()
        except FileNotFoundError:
            if self._state_was_established:
                raise ValueError("persisted fencing state disappeared after being established")
            return None
        return self._decode_state(raw)

    def _persist_and_reload(self, counter: int) -> DurableProtectedResourceFencingState:
        expected = self._canonical_bytes(counter)
        fd, temp_name = tempfile.mkstemp(prefix=f".{self._state_path.name}.", suffix=".tmp", dir=self._state_path.parent)
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(expected)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self._state_path)
            reloaded = self._state_path.read_bytes()
            if reloaded != expected:
                raise ValueError("persisted fencing state bytes differ after replacement")
            state = self._decode_state(reloaded)
            if state.highest_accepted_fencing_counter != counter:
                raise ValueError("persisted fencing counter differs after replacement")
            self._state_was_established = True
            return state
        finally:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass

    def validate_fencing_token(
        self,
        resource_id: str,
        fencing_authority_id: str,
        fencing_counter: int,
    ) -> ProtectedResourceFencingDecision:
        resource_id = self._require_identity(resource_id, "resource_id")
        fencing_authority_id = self._require_identity(fencing_authority_id, "fencing_authority_id")
        fencing_counter = self._require_counter(fencing_counter)
        if resource_id != self._resource_id:
            raise ValueError("resource_id does not match durable adapter identity")
        if fencing_authority_id != self._fencing_authority_id:
            raise ValueError("fencing_authority_id does not match durable adapter identity")

        with self._lock:
            current = self._load_state()
            current_counter = None if current is None else current.highest_accepted_fencing_counter
            accepted = current_counter is None or fencing_counter >= current_counter
            if accepted and (current_counter is None or fencing_counter > current_counter):
                self._persist_and_reload(fencing_counter)

        return ProtectedResourceFencingDecision(
            resource_id=resource_id,
            fencing_authority_id=fencing_authority_id,
            fencing_counter=fencing_counter,
            accepted=accepted,
        )

    def snapshot(self) -> DurableProtectedResourceFencingState | None:
        with self._lock:
            return self._load_state()

    @property
    def automatic_control_allowed(self) -> bool:
        return False

    @property
    def activation_allowed(self) -> bool:
        return False

    @property
    def traffic_switching_allowed(self) -> bool:
        return False
