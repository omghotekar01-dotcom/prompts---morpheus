from __future__ import annotations

from threading import RLock

from .models import CalibrationMeasurement, CalibrationProfile, QueryDistributionSpec, QueryKind
from .storage import STORE


def _distribution_identity(distribution: QueryDistributionSpec | None) -> dict[str, object] | None:
    if distribution is None:
        return None
    return distribution.model_dump(mode="json", exclude_none=True)


class CalibrationRegistry:
    """Explicit calibration registry backed by durable local state.

    Profiles survive control-plane restarts, but activation remains explicit:
    importing/registering a profile never changes synthesis behavior unless the
    caller also activates it. The persisted active profile is restored at
    process start so a deliberate operator choice is durable and auditable.

    Measurement lookup is implementation- and distribution-aware. A primitive
    label alone is not sufficient evidence because MORPHEUS has historically had
    multiple physical implementations behind names such as `ordered_tree` and
    `bitmap`, and access locality can materially alter observed latency. Callers
    that provide expected identities receive only exact matches; legacy,
    unlabeled, stale, or differently skewed measurements are ignored rather than
    silently contaminating the cost model.
    """

    def __init__(self) -> None:
        profiles, active_profile_id = STORE.load_calibration_profiles()
        self._profiles: dict[str, CalibrationProfile] = {profile.id: profile for profile in profiles}
        self._active_profile_id: str | None = active_profile_id
        self._lock = RLock()

    def register(self, profile: CalibrationProfile, *, persist: bool = True) -> CalibrationProfile:
        with self._lock:
            self._profiles[profile.id] = profile
            if persist:
                STORE.save_calibration_profile(profile, activate=False)
            return profile

    def list_profiles(self) -> list[CalibrationProfile]:
        with self._lock:
            return [self._profiles[key] for key in sorted(self._profiles)]

    def get(self, profile_id: str) -> CalibrationProfile:
        with self._lock:
            try:
                return self._profiles[profile_id]
            except KeyError as exc:
                raise KeyError(f"unknown calibration profile: {profile_id}") from exc

    def activate(self, profile_id: str, *, persist: bool = True) -> CalibrationProfile:
        with self._lock:
            profile = self.get(profile_id)
            if persist:
                STORE.save_calibration_profile(profile, activate=True)
            self._active_profile_id = profile_id
            return profile

    def deactivate(self, *, persist: bool = True) -> None:
        with self._lock:
            if persist:
                STORE.set_active_calibration(None)
            self._active_profile_id = None

    def active(self) -> CalibrationProfile | None:
        with self._lock:
            if self._active_profile_id is None:
                return None
            return self._profiles.get(self._active_profile_id)

    @property
    def active_profile_id(self) -> str | None:
        with self._lock:
            return self._active_profile_id

    def measurement(
        self,
        primitive: str,
        operation: str | QueryKind,
        *,
        profile: CalibrationProfile | None = None,
        expected_implementation_id: str | None = None,
        expected_distribution: QueryDistributionSpec | None = None,
        require_distribution_identity: bool = False,
    ) -> CalibrationMeasurement | None:
        """Return the strongest exact measurement satisfying requested provenance.

        `require_distribution_identity=True` distinguishes two very different
        requests: a caller asking for a query/update measurement with an exact
        distribution, versus a distribution-independent operation such as build.
        When identity is required, an unlabeled legacy measurement cannot match.
        """

        selected = profile or self.active()
        if selected is None:
            return None
        operation_name = operation.value if isinstance(operation, QueryKind) else operation
        expected_distribution_identity = _distribution_identity(expected_distribution)

        matches: list[CalibrationMeasurement] = []
        for item in selected.measurements:
            if item.primitive != primitive or item.operation != operation_name:
                continue
            if expected_implementation_id is not None and item.implementation_id != expected_implementation_id:
                continue
            if require_distribution_identity:
                if item.access_distribution is None:
                    continue
                if _distribution_identity(item.access_distribution) != expected_distribution_identity:
                    continue
            matches.append(item)

        if not matches:
            return None
        matches.sort(
            key=lambda item: (
                -item.repetitions,
                item.stdev_ns if item.stdev_ns is not None else float("inf"),
                item.ns_per_op,
            )
        )
        return matches[0]


CALIBRATIONS = CalibrationRegistry()


def profile_from_smoke_payload(payload: dict) -> CalibrationProfile:
    """Normalize `morpheus_calibrate` JSON into the backend profile contract.

    Legacy payloads without implementation or access-distribution IDs remain
    importable for provenance, but exact implementation/distribution-aware cost
    lookups will not consume those unlabeled measurements. This is intentional:
    MORPHEUS remeasures the actual current physical implementation and declared
    access pattern rather than inferring identity from a historical name.
    """

    profile_id = str(payload.get("profile_id") or f"smoke-{payload.get('seed', 0)}-{payload.get('n', 0)}")
    raw_measurements = payload.get("measurements")
    if not isinstance(raw_measurements, list) or not raw_measurements:
        raise ValueError("calibration payload must include non-empty measurements")

    measurements = [CalibrationMeasurement.model_validate(item) for item in raw_measurements]
    machine = {str(k): str(v) for k, v in dict(payload.get("machine", {})).items()}
    for source_key, target_key in (
        ("repetitions", "profile_repetitions"),
        ("warmup_repetitions", "warmup_repetitions"),
        ("checksum", "checksum"),
        ("distribution_protocol", "distribution_protocol"),
    ):
        if source_key in payload:
            machine[target_key] = str(payload[source_key])

    return CalibrationProfile(
        id=profile_id,
        schema_version=int(payload.get("schema_version", 1)),
        evidence_state=str(payload.get("evidence_state", "MEASURED_LOCAL_PROCESS")),
        protocol=str(payload.get("protocol", "morpheus-calibration-smoke-v1")),
        record_count=int(payload.get("record_count", payload.get("n", 0))),
        operations=int(payload.get("operations", 0)),
        seed=int(payload.get("seed", 0)),
        machine=machine,
        measurements=measurements,
        notes=str(payload.get("notes", "Imported from calibration JSON payload.")),
    )
