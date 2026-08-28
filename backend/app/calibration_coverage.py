from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .catalog import PRIMITIVES
from .models import CalibrationProfile, QueryKind


_MUTATIONS = {QueryKind.INSERT, QueryKind.UPDATE, QueryKind.DELETE}


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


def audit_calibration_coverage(
    profile: CalibrationProfile,
    *,
    primitive_names: Iterable[str] | None = None,
) -> CalibrationCoverageReport:
    names = sorted(set(primitive_names) if primitive_names is not None else PRIMITIVES)
    unknown = [name for name in names if name not in PRIMITIVES]
    if unknown:
        raise ValueError(f"unknown primitives in calibration coverage request: {unknown}")

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
