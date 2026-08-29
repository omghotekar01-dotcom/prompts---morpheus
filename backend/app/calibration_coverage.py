from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .catalog import PRIMITIVES
from .models import CalibrationProfile, QueryDistributionSpec, QueryKind, WorkloadSpec


_MUTATIONS = {QueryKind.INSERT, QueryKind.UPDATE, QueryKind.DELETE}


def _distribution_identity(distribution: QueryDistributionSpec | None) -> dict[str, object] | None:
    if distribution is None:
        return None
    return distribution.model_dump(mode="json", exclude_none=True)


@dataclass(frozen=True)
class CalibrationCoverageCell:
    primitive: str
    implementation_id: str
    operation: str
    status: str
    matching_measurements: int
    stale_measurements: int

    def as_dict(self) -> dict[str, object]:
        return {
            "primitive": self.primitive,
            "implementation_id": self.implementation_id,
            "operation": self.operation,
            "status": self.status,
            "matching_measurements": self.matching_measurements,
            "stale_measurements": self.stale_measurements,
        }


@dataclass(frozen=True)
class CalibrationCoverageReport:
    profile_id: str
    required_cells: int
    matched_cells: int
    missing_cells: int
    stale_only_cells: int
    coverage_ratio: float
    cells: tuple[CalibrationCoverageCell, ...]
    evidence_state: str = "CALIBRATION_COVERAGE_AUDITED_NOT_PERFORMANCE_EVIDENCE"

    def as_dict(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "required_cells": self.required_cells,
            "matched_cells": self.matched_cells,
            "missing_cells": self.missing_cells,
            "stale_only_cells": self.stale_only_cells,
            "coverage_ratio": self.coverage_ratio,
            "cells": [cell.as_dict() for cell in self.cells],
            "evidence_state": self.evidence_state,
            "truth_boundary": (
                "Coverage means a profile contains measurements whose primitive, operation and physical implementation_id match the current catalog. "
                "It does not establish that the measurements are statistically sufficient, current for this machine, or accurate end-to-end."
            ),
        }


@dataclass(frozen=True)
class WorkloadDistributionCoverageCell:
    query_index: int
    primitive: str
    implementation_id: str
    operation: str
    access_distribution: dict[str, object]
    status: str
    exact_measurements: int
    implementation_matches: int
    stale_measurements: int

    def as_dict(self) -> dict[str, object]:
        return {
            "query_index": self.query_index,
            "primitive": self.primitive,
            "implementation_id": self.implementation_id,
            "operation": self.operation,
            "access_distribution": self.access_distribution,
            "status": self.status,
            "exact_measurements": self.exact_measurements,
            "implementation_matches": self.implementation_matches,
            "stale_measurements": self.stale_measurements,
        }


@dataclass(frozen=True)
class WorkloadDistributionCoverageReport:
    profile_id: str
    workload_name: str
    record_count: int
    profile_record_count: int
    scale_matches_profile: bool
    required_cells: int
    matched_cells: int
    distribution_mismatch_cells: int
    scale_mismatch_cells: int
    stale_only_cells: int
    missing_cells: int
    coverage_ratio: float
    cells: tuple[WorkloadDistributionCoverageCell, ...]
    evidence_state: str = "WORKLOAD_DISTRIBUTION_CALIBRATION_COVERAGE_AUDITED_NOT_PERFORMANCE_EVIDENCE"

    def as_dict(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "workload_name": self.workload_name,
            "record_count": self.record_count,
            "profile_record_count": self.profile_record_count,
            "scale_matches_profile": self.scale_matches_profile,
            "required_cells": self.required_cells,
            "matched_cells": self.matched_cells,
            "distribution_mismatch_cells": self.distribution_mismatch_cells,
            "scale_mismatch_cells": self.scale_mismatch_cells,
            "stale_only_cells": self.stale_only_cells,
            "missing_cells": self.missing_cells,
            "coverage_ratio": self.coverage_ratio,
            "cells": [cell.as_dict() for cell in self.cells],
            "evidence_state": self.evidence_state,
            "truth_boundary": (
                "A MATCHED cell means workload scale, operation, physical implementation ID and complete declared access-distribution parameters match exactly. "
                "Coverage is an evidence-inventory audit only: it does not prove statistical sufficiency, cross-machine transfer, interpolation validity, or end-to-end candidate performance."
            ),
        }


def required_operations(primitive_name: str) -> tuple[str, ...]:
    try:
        primitive = PRIMITIVES[primitive_name]
    except KeyError as exc:
        raise ValueError(f"unknown primitive: {primitive_name}") from exc

    operations = {"build"}
    operations.update(kind.value for kind in primitive.capabilities if kind not in _MUTATIONS)
    # Generated record-backed indexes are maintained on update even when the
    # public query-capability set is read-only. CSR topology is externally
    # configured and is intentionally excluded from record-update calibration.
    if primitive_name != "csr_graph":
        operations.add("update")
    return tuple(sorted(operations))


def _validated_names(primitive_names: Iterable[str] | None) -> list[str]:
    names = sorted(set(primitive_names) if primitive_names is not None else PRIMITIVES)
    unknown = [name for name in names if name not in PRIMITIVES]
    if unknown:
        raise ValueError(f"unknown primitives in calibration coverage request: {unknown}")
    return names


def audit_calibration_coverage(
    profile: CalibrationProfile,
    *,
    primitive_names: Iterable[str] | None = None,
) -> CalibrationCoverageReport:
    names = _validated_names(primitive_names)

    cells: list[CalibrationCoverageCell] = []
    for primitive_name in names:
        primitive = PRIMITIVES[primitive_name]
        for operation in required_operations(primitive_name):
            same_name_operation = [
                measurement
                for measurement in profile.measurements
                if measurement.primitive == primitive_name and measurement.operation == operation
            ]
            matching = [
                measurement
                for measurement in same_name_operation
                if measurement.implementation_id == primitive.implementation_id
            ]
            stale = [
                measurement
                for measurement in same_name_operation
                if measurement.implementation_id != primitive.implementation_id
            ]
            status = "MATCHED" if matching else ("STALE_ONLY" if stale else "MISSING")
            cells.append(
                CalibrationCoverageCell(
                    primitive=primitive_name,
                    implementation_id=primitive.implementation_id,
                    operation=operation,
                    status=status,
                    matching_measurements=len(matching),
                    stale_measurements=len(stale),
                )
            )

    matched = sum(cell.status == "MATCHED" for cell in cells)
    missing = sum(cell.status == "MISSING" for cell in cells)
    stale_only = sum(cell.status == "STALE_ONLY" for cell in cells)
    return CalibrationCoverageReport(
        profile_id=profile.id,
        required_cells=len(cells),
        matched_cells=matched,
        missing_cells=missing,
        stale_only_cells=stale_only,
        coverage_ratio=(matched / len(cells)) if cells else 1.0,
        cells=tuple(cells),
    )


def audit_workload_distribution_coverage(
    profile: CalibrationProfile,
    spec: WorkloadSpec,
    *,
    primitive_names: Iterable[str] | None = None,
) -> WorkloadDistributionCoverageReport:
    """Audit exact distribution-bound evidence available for one workload.

    Read operations are checked only against primitive families that declare the
    corresponding query capability. Declared record mutations are checked
    against every selected record-backed primitive because generated indexes are
    physically maintained on INSERT/UPDATE/DELETE even if they do not expose
    those operations as standalone query routes. CSR is excluded from ordinary
    record mutation maintenance because graph topology is configured separately.
    """

    names = _validated_names(primitive_names)
    scale_matches = spec.record_count == profile.record_count
    cells: list[WorkloadDistributionCoverageCell] = []

    for query_index, query in enumerate(spec.queries):
        if query.kind in _MUTATIONS:
            applicable_names = [name for name in names if name != "csr_graph"]
        else:
            applicable_names = [
                name for name in names if query.kind in PRIMITIVES[name].capabilities
            ]

        expected_distribution = _distribution_identity(query.distribution)
        assert expected_distribution is not None
        for primitive_name in applicable_names:
            primitive = PRIMITIVES[primitive_name]
            same_operation = [
                measurement
                for measurement in profile.measurements
                if measurement.primitive == primitive_name
                and measurement.operation == query.kind.value
            ]
            implementation_matches = [
                measurement
                for measurement in same_operation
                if measurement.implementation_id == primitive.implementation_id
            ]
            exact = [
                measurement
                for measurement in implementation_matches
                if _distribution_identity(measurement.access_distribution) == expected_distribution
            ]
            stale = [
                measurement
                for measurement in same_operation
                if measurement.implementation_id != primitive.implementation_id
            ]

            if exact and scale_matches:
                status = "MATCHED"
            elif exact:
                status = "SCALE_MISMATCH"
            elif implementation_matches:
                status = "DISTRIBUTION_MISMATCH"
            elif stale:
                status = "STALE_ONLY"
            else:
                status = "MISSING"

            cells.append(
                WorkloadDistributionCoverageCell(
                    query_index=query_index,
                    primitive=primitive_name,
                    implementation_id=primitive.implementation_id,
                    operation=query.kind.value,
                    access_distribution=expected_distribution,
                    status=status,
                    exact_measurements=len(exact),
                    implementation_matches=len(implementation_matches),
                    stale_measurements=len(stale),
                )
            )

    matched = sum(cell.status == "MATCHED" for cell in cells)
    mismatched = sum(cell.status == "DISTRIBUTION_MISMATCH" for cell in cells)
    scale_mismatch = sum(cell.status == "SCALE_MISMATCH" for cell in cells)
    stale_only = sum(cell.status == "STALE_ONLY" for cell in cells)
    missing = sum(cell.status == "MISSING" for cell in cells)
    return WorkloadDistributionCoverageReport(
        profile_id=profile.id,
        workload_name=spec.name,
        record_count=spec.record_count,
        profile_record_count=profile.record_count,
        scale_matches_profile=scale_matches,
        required_cells=len(cells),
        matched_cells=matched,
        distribution_mismatch_cells=mismatched,
        scale_mismatch_cells=scale_mismatch,
        stale_only_cells=stale_only,
        missing_cells=missing,
        coverage_ratio=(matched / len(cells)) if cells else 1.0,
        cells=tuple(cells),
    )
