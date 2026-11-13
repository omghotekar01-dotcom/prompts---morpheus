from __future__ import annotations

"""Implementation-aware, provenance-labeled *estimated* index memory footprint."""

from .catalog import PRIMITIVES
from .models import WorkloadSpec

# A compressed equality index stores a distinct-key -> posting-list directory.
# Its overhead cannot be modeled as a constant number of bytes per record.
# The per-key figure below is a bootstrap engineering prior, not a measured
# value on the user's hardware; local RSS calibration must replace it.
_BOOTSTRAP_BITMAP_DIRECTORY_BYTES_PER_DISTINCT_KEY = 48.0


def predicted_index_bytes(spec: WorkloadSpec, primitive_name: str, field_name: str | None) -> float:
    primitive = PRIMITIVES[primitive_name]
    estimate = primitive.memory_bytes_per_record * spec.record_count
    if primitive_name == "bitmap" and field_name is not None:
        cardinality = next(
            (field.cardinality for field in spec.fields if field.name == field_name),
            None,
        )
        if cardinality is not None:
            estimate += _BOOTSTRAP_BITMAP_DIRECTORY_BYTES_PER_DISTINCT_KEY * cardinality
    return estimate
