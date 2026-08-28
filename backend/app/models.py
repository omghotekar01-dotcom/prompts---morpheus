from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator


class QueryKind(str, Enum):
    POINT_LOOKUP = "point_lookup"
    RANGE_SCAN = "range_scan"
    FILTER = "filter"
    PREFIX_SEARCH = "prefix_search"
    GRAPH_TRAVERSAL = "graph_traversal"
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"


class SearchStrategy(str, Enum):
    AUTO = "auto"
    EXHAUSTIVE = "exhaustive"
    GREEDY = "greedy"
    BEAM = "beam"


class FieldSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    type: str = Field(min_length=1, max_length=64)
    cardinality: int | None = Field(default=None, ge=1)


class QuerySpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: QueryKind
    field: str | None = None
    weight: float = Field(default=1.0, gt=0)
    selectivity: float | None = Field(default=None, gt=0, le=1)
    result_limit: int | None = Field(default=None, ge=1)
    prefix_length: int | None = Field(default=None, ge=1)

    # Resolution provenance must not leak into canonical MWS serialization or
    # semantic hashes. Pydantic assignment inside an after-validator updates
    # model_fields_set, so a private flag records whether MORPHEUS—not the user—
    # supplied the resolved selectivity.
    _selectivity_defaulted: bool = PrivateAttr(default=False)

    @property
    def selectivity_defaulted(self) -> bool:
        return self._selectivity_defaulted


class Constraints(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_mb: float | None = Field(default=None, gt=0)
    p99_latency_us: float | None = Field(default=None, gt=0)
    update_rate: float = Field(default=0.0, ge=0)
    build_time_ms: float | None = Field(default=None, gt=0)


class ObjectiveWeights(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latency: float = Field(default=1.0, ge=0)
    memory: float = Field(default=0.15, ge=0)
    update: float = Field(default=0.2, ge=0)
    build: float = Field(default=0.05, ge=0)

    @model_validator(mode="after")
    def at_least_one_positive(self) -> "ObjectiveWeights":
        if self.latency + self.memory + self.update + self.build <= 0:
            raise ValueError("at least one objective weight must be positive")
        return self


class WorkloadSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = "mws-0.1"
    name: str = Field(default="workload", min_length=1, max_length=128)
    record_count: int = Field(default=100_000, ge=1, le=1_000_000_000)
    fields: list[FieldSpec] = Field(min_length=1, max_length=64)
    queries: list[QuerySpec] = Field(min_length=1, max_length=32)
    constraints: Constraints = Field(default_factory=Constraints)
    objective: ObjectiveWeights = Field(default_factory=ObjectiveWeights)

    @model_validator(mode="after")
    def semantic_validation(self) -> "WorkloadSpec":
        field_names = [item.name for item in self.fields]
        if len(field_names) != len(set(field_names)):
            raise ValueError("field names must be unique")

        known = set(field_names)
        field_required = {
            QueryKind.POINT_LOOKUP,
            QueryKind.RANGE_SCAN,
            QueryKind.FILTER,
            QueryKind.PREFIX_SEARCH,
        }
        for query in self.queries:
            if query.kind in field_required and not query.field:
                raise ValueError(f"{query.kind.value} requires a field")
            if query.field and query.field not in known:
                raise ValueError(f"query references unknown field: {query.field}")
            if query.kind in {QueryKind.RANGE_SCAN, QueryKind.FILTER} and query.selectivity is None:
                query._selectivity_defaulted = True
                query.selectivity = 0.05
        return self


class PrimitiveSpec(BaseModel):
    name: str
    display_name: str
    capabilities: set[QueryKind]
    base_latency_us: dict[QueryKind, float]
    memory_bytes_per_record: float = Field(gt=0)
    build_ns_per_record: float = Field(ge=0)
    update_latency_us: float = Field(ge=0)
    notes: str = ""


class CalibrationMeasurement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primitive: str = Field(min_length=1, max_length=128)
    operation: str = Field(min_length=1, max_length=128)
    ns_per_op: float = Field(gt=0)
    repetitions: int = Field(default=1, ge=1, le=1000)
    stdev_ns: float | None = Field(default=None, ge=0)
    mean_ns: float | None = Field(default=None, gt=0)
    median_ns: float | None = Field(default=None, gt=0)
    min_ns: float | None = Field(default=None, gt=0)
    max_ns: float | None = Field(default=None, gt=0)
    samples_ns: list[float] = Field(default_factory=list, max_length=1000)

    @model_validator(mode="after")
    def validate_samples(self) -> "CalibrationMeasurement":
        if any(sample <= 0 for sample in self.samples_ns):
            raise ValueError("calibration samples must be positive")
        if self.samples_ns and len(self.samples_ns) != self.repetitions:
            raise ValueError("samples_ns length must equal repetitions when raw samples are present")
        return self


class CalibrationProfile(BaseModel):
    """Compact provenance-carrying target-machine calibration artifact."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    schema_version: int = Field(default=1, ge=1)
    evidence_state: str = "MEASURED_LOCAL_PROCESS"
    protocol: str = Field(min_length=1, max_length=128)
    record_count: int = Field(ge=1)
    operations: int = Field(ge=1)
    seed: int = Field(default=1337, ge=0)
    machine: dict[str, str] = Field(default_factory=dict)
    measurements: list[CalibrationMeasurement] = Field(min_length=1)
    notes: str = ""


class Assignment(BaseModel):
    query_index: int
    query_kind: QueryKind
    field: str | None
    primitive: str


class CandidateResult(BaseModel):
    id: str
    assignments: list[Assignment]
    unique_primitives: list[str]
    predicted_latency_us: float
    predicted_memory_mb: float
    predicted_build_ms: float
    predicted_update_us: float
    score: float
    feasible: bool
    rejection_reasons: list[str] = Field(default_factory=list)
    prediction_source: str = "BOOTSTRAP_PRIOR"
    uncertainty_ratio: float = Field(default=0.50, ge=0)


class SearchSummary(BaseModel):
    strategy: SearchStrategy
    theoretical_configurations: int = Field(ge=0)
    evaluated_configurations: int = Field(ge=0)
    feasible_configurations: int = Field(ge=0)
    truncated: bool = False
    max_candidates: int = Field(ge=1)
    beam_width: int | None = Field(default=None, ge=1)


class SynthesisResult(BaseModel):
    spec_hash: str
    workload_ir_hash: str | None = None
    workload_ir_version: str | None = None
    evidence_state: str = "PREDICTED_NOT_MEASURED"
    winner: CandidateResult | None
    candidates: list[CandidateResult]
    generated_code: str | None = None
    explanation: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    search_summary: SearchSummary | None = None
    pareto_front: list[CandidateResult] = Field(default_factory=list)
    active_calibration_profile: str | None = None


class ObservedWorkloadSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_mix: dict[QueryKind, float]
    expected_future_queries: int = Field(default=100_000, ge=1)
    observed_p99_latency_us: float | None = Field(default=None, gt=0)
    sequence: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_mix(self) -> "ObservedWorkloadSnapshot":
        total = sum(self.operation_mix.values())
        if total <= 0:
            raise ValueError("operation_mix must have positive total weight")
        if any(value < 0 for value in self.operation_mix.values()):
            raise ValueError("operation_mix weights cannot be negative")
        return self


class WorkloadDrift(BaseModel):
    distance: float = Field(ge=0, le=1)
    threshold: float = Field(ge=0, le=1)
    drifted: bool
    explanation: str


class AdaptationDecision(BaseModel):
    action: str
    predicted_benefit_us: float
    estimated_switching_cost_us: float
    threshold_us: float
    reason: str
    evidence_state: str = "PREDICTED_NOT_MEASURED"
    drift: WorkloadDrift | None = None
    cooldown_blocked: bool = False


class ApiError(BaseModel):
    detail: str
    context: dict[str, Any] = Field(default_factory=dict)
