from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .artifact_codegen import GeneratedArtifact, generate_verified_header
from .artifact_manifest import build_artifact_provenance_manifest
from .configuration_ir import lower_and_hash_configuration_ir
from .models import AccessDistribution, CandidateResult, QueryKind, WorkloadSpec
from .parser import semantic_hash
from .toolchain import base_environment, compile_command, discover_toolchain
from .workload_ir import lower_and_hash_workload_ir


REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_INCLUDE = REPO_ROOT / "core" / "include"
_MUTATION_KINDS = {QueryKind.INSERT, QueryKind.UPDATE, QueryKind.DELETE}
_DISTRIBUTION_PROTOCOL = "morpheus-access-distribution-v1"


@dataclass(frozen=True)
class CandidateBenchmarkResult:
    success: bool
    evidence_state: str
    candidate_id: str
    spec_hash: str
    workload_ir_hash: str
    configuration_ir_hash: str
    primitive_manifest_hash: str
    generated_source_sha256: str
    driver_sha256: str
    compiler: str | None
    compiler_kind: str | None
    compiler_version: str | None
    compile_returncode: int | None
    run_returncode: int | None
    record_count: int
    operations: int
    repetitions: int
    warmup_repetitions: int
    measurements: tuple[dict[str, Any], ...]
    checksum: int | None
    distribution_protocol: str = _DISTRIBUTION_PROTOCOL
    query_distributions: tuple[dict[str, Any], ...] = ()
    compile_stdout: str = ""
    compile_stderr: str = ""
    run_stdout: str = ""
    run_stderr: str = ""
    limitations: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "evidence_state": self.evidence_state,
            "candidate_id": self.candidate_id,
            "spec_hash": self.spec_hash,
            "workload_ir_hash": self.workload_ir_hash,
            "configuration_ir_hash": self.configuration_ir_hash,
            "primitive_manifest_hash": self.primitive_manifest_hash,
            "generated_source_sha256": self.generated_source_sha256,
            "driver_sha256": self.driver_sha256,
            "compiler": self.compiler,
            "compiler_kind": self.compiler_kind,
            "compiler_version": self.compiler_version,
            "compile_returncode": self.compile_returncode,
            "run_returncode": self.run_returncode,
            "record_count": self.record_count,
            "operations": self.operations,
            "repetitions": self.repetitions,
            "warmup_repetitions": self.warmup_repetitions,
            "measurements": list(self.measurements),
            "checksum": self.checksum,
            "distribution_protocol": self.distribution_protocol,
            "query_distributions": list(self.query_distributions),
            "compile_stdout": self.compile_stdout,
            "compile_stderr": self.compile_stderr,
            "run_stdout": self.run_stdout,
            "run_stderr": self.run_stderr,
            "limitations": list(self.limitations),
            "truth_boundary": (
                "Successful output is a repeated local-process measurement of one generated candidate on the discovered toolchain. "
                "Declared query access distributions are precomputed outside timed query loops and are bound by WorkloadIR/source hashes. "
                "It is not publication-grade, cross-machine, production-SLA, or state-of-the-art evidence by itself."
            ),
        }


def _normalized_type(raw: str) -> str:
    lowered = raw.lower()
    if lowered in {"uint64", "uint64_t", "uint32", "uint32_t", "int", "integer"}:
        return "integer"
    if lowered in {"float", "double"}:
        return "floating"
    if lowered in {"bool", "boolean"}:
        return "bool"
    return "string"


def _cpp_type(raw: str) -> str:
    lowered = raw.lower()
    return {
        "uint64": "std::uint64_t",
        "uint64_t": "std::uint64_t",
        "uint32": "std::uint32_t",
        "uint32_t": "std::uint32_t",
        "int": "std::int64_t",
        "integer": "std::int64_t",
        "float": "double",
        "double": "double",
        "bool": "bool",
        "boolean": "bool",
        "string": "std::string",
        "str": "std::string",
        "text": "std::string",
    }.get(lowered, "std::string")


def _field_expression(raw_type: str, field_index: int, cardinality: int | None) -> str:
    domain = "row" if cardinality is None else f"(row % {max(1, cardinality)})"
    kind = _normalized_type(raw_type)
    cpp_type = _cpp_type(raw_type)
    if kind == "integer":
        return f"static_cast<{cpp_type}>(({domain}) * 100ULL + {field_index + 1}ULL)"
    if kind == "floating":
        return f"static_cast<double>(({domain}) * 10.0 + {field_index}.25)"
    if kind == "bool":
        return f"static_cast<bool>(({domain} + {field_index}) % 2)"
    return f"field_string({field_index}, static_cast<std::uint64_t>({domain}))"


def _record_factory(spec: WorkloadSpec) -> str:
    expressions = [
        _field_expression(field.type, index, field.cardinality)
        for index, field in enumerate(spec.fields)
    ]
    return "    return Record{" + ", ".join(expressions) + "};"


def _distribution_declaration(spec: WorkloadSpec, query_index: int) -> str:
    query = spec.queries[query_index]
    distribution = query.distribution
    seed = 0xA0761D6478BD642F + query_index * 0x9E3779B97F4A7C15
    variable = f"q{query_index}_rows"
    if distribution.kind == AccessDistribution.UNIFORM:
        return f"        const auto {variable} = make_uniform_rows(n, operations, {seed & ((1 << 64) - 1)}ULL);"
    if distribution.kind == AccessDistribution.SEQUENTIAL:
        return f"        const auto {variable} = make_sequential_rows(n, operations);"
    if distribution.kind == AccessDistribution.HOTSPOT:
        return (
            f"        const auto {variable} = make_hotspot_rows(n, operations, "
            f"{distribution.hotspot_fraction:.17g}, {distribution.hotspot_probability:.17g}, "
            f"{seed & ((1 << 64) - 1)}ULL);"
        )
    if distribution.kind == AccessDistribution.ZIPF:
        return (
            f"        const auto {variable} = make_zipf_rows(n, operations, "
            f"{distribution.zipf_theta:.17g}, {seed & ((1 << 64) - 1)}ULL);"
        )
    raise ValueError(f"unsupported distribution: {distribution.kind}")


def _route_block(spec: WorkloadSpec, assignment) -> str:
    method = f"query_{assignment.query_index}"
    kind = assignment.query_kind
    rows = f"q{assignment.query_index}_rows"
    if kind == QueryKind.GRAPH_TRAVERSAL:
        return f'''        measurements.push_back(measure("query_{assignment.query_index}", "graph_traversal", operations, repetitions, warmup, [&](std::size_t) {{
            for (std::size_t i = 0; i < operations; ++i) {{
                const auto start = static_cast<std::uint32_t>({rows}[i]);
                checksum += index.{method}(start, 4).size();
            }}
        }}));'''

    if assignment.field is None:
        raise ValueError(f"candidate route {assignment.query_index} lacks a field")
    field_name = assignment.field
    query = spec.queries[assignment.query_index]

    if kind in {QueryKind.POINT_LOOKUP, QueryKind.FILTER}:
        body = f'''const auto record = make_record({rows}[i]);
                checksum += index.{method}(record.{field_name}).size();'''
    elif kind == QueryKind.RANGE_SCAN:
        body = f'''auto low = make_record({rows}[i]).{field_name};
                auto high = make_record({rows}[(i + 7) % operations]).{field_name};
                if (high < low) std::swap(low, high);
                checksum += index.{method}(low, high).size();'''
    elif kind == QueryKind.PREFIX_SEARCH:
        prefix_length = max(1, query.prefix_length or 12)
        limit = query.result_limit or 64
        body = f'''const auto record = make_record({rows}[i]);
                const auto prefix = record.{field_name}.substr(0, std::min<std::size_t>({prefix_length}, record.{field_name}.size()));
                checksum += index.{method}(prefix, {limit}).size();'''
    else:
        raise ValueError(f"unsupported read route in candidate benchmark: {kind.value}")

    return f'''        measurements.push_back(measure("query_{assignment.query_index}", "{kind.value}", operations, repetitions, warmup, [&](std::size_t) {{
            for (std::size_t i = 0; i < operations; ++i) {{
                {body}
            }}
        }}));'''


def _graph_configuration_blocks(candidate: CandidateResult, variable: str) -> str:
    blocks: list[str] = []
    for assignment in candidate.assignments:
        if assignment.query_kind == QueryKind.GRAPH_TRAVERSAL:
            blocks.append(
                f"        {variable}.configure_graph_{assignment.query_index}(n, make_chain_edges(n), true);"
            )
    return "\n".join(blocks)


def generate_candidate_benchmark_driver(
    spec: WorkloadSpec,
    candidate: CandidateResult,
    artifact: GeneratedArtifact,
) -> str:
    read_assignments = [
        assignment for assignment in candidate.assignments if assignment.query_kind not in _MUTATION_KINDS
    ]
    if not read_assignments:
        raise ValueError("candidate benchmark requires at least one queryable route")

    route_blocks = "\n".join(_route_block(spec, assignment) for assignment in read_assignments)
    distribution_declarations = "\n".join(
        _distribution_declaration(spec, assignment.query_index) for assignment in read_assignments
    )
    candidate_graph_configuration = _graph_configuration_blocks(candidate, "candidate")
    index_graph_configuration = _graph_configuration_blocks(candidate, "index")
    has_record_backed_route = any(
        assignment.query_kind != QueryKind.GRAPH_TRAVERSAL for assignment in read_assignments
    )
    update_block = ""
    if has_record_backed_route:
        update_block = '''        const auto maintenance_rows = make_uniform_rows(n, operations, 1469598103934665603ULL);
        measurements.push_back(measure("generated_candidate", "update_record", operations, repetitions, warmup, [&](std::size_t rep) {
            for (std::size_t i = 0; i < operations; ++i) {
                const auto position = maintenance_rows[i];
                index.update_at(position, make_record(n + i + rep + 1));
            }
        }));'''

    return f'''#include "{artifact.header_name}"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

using Index = {artifact.namespace_name}::GeneratedIndex;
using Record = Index::Record;

struct Measurement {{
    std::string name;
    std::string operation;
    double median_ns;
    double mean_ns;
    double stdev_ns;
    double min_ns;
    double max_ns;
    std::vector<double> samples_ns;
}};

void print_json_string(std::string_view value) {{
    std::cout << static_cast<char>(34) << value << static_cast<char>(34);
}}

void print_key(std::string_view key) {{
    print_json_string(key);
    std::cout << ':';
}}

std::string field_string(std::size_t field, std::uint64_t value) {{
    std::ostringstream stream;
    stream << 'f' << field << "_value_" << std::setw(12) << std::setfill('0') << value;
    return stream.str();
}}

Record make_record(std::size_t row) {{
{_record_factory(spec)}
}}

std::uint64_t mix64(std::uint64_t value) {{
    value += 0x9E3779B97F4A7C15ULL;
    value = (value ^ (value >> 30U)) * 0xBF58476D1CE4E5B9ULL;
    value = (value ^ (value >> 27U)) * 0x94D049BB133111EBULL;
    return value ^ (value >> 31U);
}}

double unit_interval(std::uint64_t value) {{
    return static_cast<double>(value >> 11U) * (1.0 / 9007199254740992.0);
}}

std::vector<std::size_t> make_uniform_rows(std::size_t n, std::size_t operations, std::uint64_t seed) {{
    if (n == 0) throw std::runtime_error("empty benchmark dataset");
    std::vector<std::size_t> rows;
    rows.reserve(operations);
    for (std::size_t i = 0; i < operations; ++i) {{
        rows.push_back(static_cast<std::size_t>(mix64(seed + i) % n));
    }}
    return rows;
}}

std::vector<std::size_t> make_sequential_rows(std::size_t n, std::size_t operations) {{
    if (n == 0) throw std::runtime_error("empty benchmark dataset");
    std::vector<std::size_t> rows;
    rows.reserve(operations);
    for (std::size_t i = 0; i < operations; ++i) rows.push_back(i % n);
    return rows;
}}

std::vector<std::size_t> make_hotspot_rows(
    std::size_t n,
    std::size_t operations,
    double hotspot_fraction,
    double hotspot_probability,
    std::uint64_t seed
) {{
    if (n == 0) throw std::runtime_error("empty benchmark dataset");
    if (!(hotspot_fraction > 0.0 && hotspot_fraction <= 1.0)) throw std::runtime_error("invalid hotspot fraction");
    if (!(hotspot_probability > 0.0 && hotspot_probability <= 1.0)) throw std::runtime_error("invalid hotspot probability");
    const auto hotspot_size = std::max<std::size_t>(1, static_cast<std::size_t>(std::ceil(n * hotspot_fraction)));
    std::vector<std::size_t> rows;
    rows.reserve(operations);
    for (std::size_t i = 0; i < operations; ++i) {{
        const auto selector = mix64(seed + i);
        const auto row_hash = mix64(selector ^ 0xD1B54A32D192ED03ULL);
        const auto domain = unit_interval(selector) < hotspot_probability ? hotspot_size : n;
        rows.push_back(static_cast<std::size_t>(row_hash % domain));
    }}
    return rows;
}}

std::vector<std::size_t> make_zipf_rows(
    std::size_t n,
    std::size_t operations,
    double theta,
    std::uint64_t seed
) {{
    if (n == 0) throw std::runtime_error("empty benchmark dataset");
    if (!(theta > 0.0 && theta <= 4.0)) throw std::runtime_error("invalid zipf theta");
    if (n > 1000000) throw std::runtime_error("zipf benchmark record count exceeds distribution safety limit");
    std::vector<double> cumulative(n);
    double total = 0.0;
    for (std::size_t rank = 1; rank <= n; ++rank) {{
        total += 1.0 / std::pow(static_cast<double>(rank), theta);
        cumulative[rank - 1] = total;
    }}
    std::vector<std::size_t> rows;
    rows.reserve(operations);
    for (std::size_t i = 0; i < operations; ++i) {{
        const auto target = unit_interval(mix64(seed + i)) * total;
        const auto position = std::lower_bound(cumulative.begin(), cumulative.end(), target);
        rows.push_back(static_cast<std::size_t>(std::distance(cumulative.begin(), position)));
    }}
    return rows;
}}

std::vector<std::pair<std::uint32_t, std::uint32_t>> make_chain_edges(std::size_t n) {{
    std::vector<std::pair<std::uint32_t, std::uint32_t>> edges;
    if (n < 2) return edges;
    edges.reserve(n - 1);
    for (std::size_t i = 1; i < n; ++i) {{
        edges.emplace_back(static_cast<std::uint32_t>(i - 1), static_cast<std::uint32_t>(i));
    }}
    return edges;
}}

template <typename Fn>
Measurement measure(
    std::string name,
    std::string operation,
    std::size_t operations,
    std::size_t repetitions,
    std::size_t warmup,
    Fn&& fn
) {{
    for (std::size_t repetition = 0; repetition < warmup; ++repetition) fn(repetition);
    std::vector<double> samples;
    samples.reserve(repetitions);
    for (std::size_t repetition = 0; repetition < repetitions; ++repetition) {{
        const auto start = std::chrono::steady_clock::now();
        fn(repetition);
        const auto stop = std::chrono::steady_clock::now();
        samples.push_back(
            std::chrono::duration<double, std::nano>(stop - start).count()
            / static_cast<double>(operations)
        );
    }}
    auto sorted = samples;
    std::sort(sorted.begin(), sorted.end());
    const double median = sorted.size() % 2 == 0
        ? (sorted[sorted.size() / 2 - 1] + sorted[sorted.size() / 2]) / 2.0
        : sorted[sorted.size() / 2];
    double mean = 0.0;
    for (const auto value : samples) mean += value;
    mean /= static_cast<double>(samples.size());
    double variance = 0.0;
    for (const auto value : samples) {{
        const auto delta = value - mean;
        variance += delta * delta;
    }}
    variance /= static_cast<double>(samples.size());
    return {{
        std::move(name), std::move(operation), median, mean, std::sqrt(variance),
        sorted.front(), sorted.back(), std::move(samples)
    }};
}}

void print_measurement(const Measurement& item) {{
    std::cout << '{{';
    print_key("name"); print_json_string(item.name); std::cout << ',';
    print_key("operation"); print_json_string(item.operation); std::cout << ',';
    print_key("median_ns"); std::cout << item.median_ns << ',';
    print_key("mean_ns"); std::cout << item.mean_ns << ',';
    print_key("stdev_ns"); std::cout << item.stdev_ns << ',';
    print_key("min_ns"); std::cout << item.min_ns << ',';
    print_key("max_ns"); std::cout << item.max_ns << ',';
    print_key("samples_ns"); std::cout << '[';
    for (std::size_t i = 0; i < item.samples_ns.size(); ++i) {{
        if (i) std::cout << ',';
        std::cout << item.samples_ns[i];
    }}
    std::cout << ']' << '}}';
}}

int main(int argc, char** argv) {{
    try {{
        std::size_t n = {min(spec.record_count, 10000)};
        std::size_t operations = 2000;
        std::size_t repetitions = 5;
        std::size_t warmup = 1;
        for (int i = 1; i < argc; ++i) {{
            const std::string_view arg = argv[i];
            auto read = [&](std::size_t& target) {{
                if (i + 1 >= argc) throw std::runtime_error("missing benchmark option value");
                target = static_cast<std::size_t>(std::stoull(argv[++i]));
            }};
            if (arg == "--n") read(n);
            else if (arg == "--ops") read(operations);
            else if (arg == "--repetitions") read(repetitions);
            else if (arg == "--warmup") read(warmup);
            else throw std::runtime_error("unknown benchmark option");
        }}
        if (n == 0 || operations == 0 || repetitions == 0) {{
            throw std::runtime_error("n/ops/repetitions must be positive");
        }}
        if (n > 10000000 || operations > 10000000 || repetitions > 100 || warmup > 20) {{
            throw std::runtime_error("benchmark safety limit exceeded");
        }}
        if (n > static_cast<std::size_t>(std::numeric_limits<std::uint32_t>::max())) {{
            throw std::runtime_error("candidate benchmark exceeds generated compressed-bitmap slot domain");
        }}

{distribution_declarations}

        std::uint64_t checksum = 0;
        std::vector<Measurement> measurements;
        measurements.push_back(measure(
            "generated_candidate", "build_end_to_end", n, repetitions, warmup,
            [&](std::size_t) {{
                Index candidate;
                for (std::size_t row = 0; row < n; ++row) candidate.insert(make_record(row));
{candidate_graph_configuration}
                checksum += candidate.size();
            }}
        ));

        Index index;
        for (std::size_t row = 0; row < n; ++row) index.insert(make_record(row));
{index_graph_configuration}

{route_blocks}
{update_block}

        std::cout << std::fixed << std::setprecision(3);
        std::cout << '{{';
        print_key("protocol"); print_json_string("morpheus-generated-candidate-benchmark-v2"); std::cout << ',';
        print_key("distribution_protocol"); print_json_string("{_DISTRIBUTION_PROTOCOL}"); std::cout << ',';
        print_key("evidence_state"); print_json_string("MEASURED_LOCAL_GENERATED_CANDIDATE_PROCESS"); std::cout << ',';
        print_key("candidate_id"); print_json_string("{candidate.id}"); std::cout << ',';
        print_key("record_count"); std::cout << n << ',';
        print_key("operations"); std::cout << operations << ',';
        print_key("repetitions"); std::cout << repetitions << ',';
        print_key("warmup_repetitions"); std::cout << warmup << ',';
        print_key("checksum"); std::cout << checksum << ',';
        print_key("measurements"); std::cout << '[';
        for (std::size_t i = 0; i < measurements.size(); ++i) {{
            if (i) std::cout << ',';
            print_measurement(measurements[i]);
        }}
        std::cout << ']' << '}}' << std::endl;
        return 0;
    }} catch (const std::exception& error) {{
        std::cerr << "morpheus candidate benchmark: " << error.what() << std::endl;
        return 2;
    }}
}}
'''


def _result_base(
    spec: WorkloadSpec,
    candidate: CandidateResult,
    artifact_manifest,
    driver_hash: str,
    workload_hash: str,
    configuration_hash: str,
    *,
    n: int,
    operations: int,
    repetitions: int,
    warmup: int,
    limitations: tuple[str, ...],
) -> dict[str, Any]:
    distributions = tuple(
        {
            "query_index": index,
            **query.distribution.model_dump(mode="json", exclude_none=True),
        }
        for index, query in enumerate(spec.queries)
        if query.kind not in _MUTATION_KINDS
    )
    return {
        "candidate_id": candidate.id,
        "spec_hash": semantic_hash(spec),
        "workload_ir_hash": workload_hash,
        "configuration_ir_hash": configuration_hash,
        "primitive_manifest_hash": artifact_manifest.primitive_manifest_hash,
        "generated_source_sha256": artifact_manifest.source_sha256,
        "driver_sha256": driver_hash,
        "record_count": n,
        "operations": operations,
        "repetitions": repetitions,
        "warmup_repetitions": warmup,
        "distribution_protocol": _DISTRIBUTION_PROTOCOL,
        "query_distributions": distributions,
        "limitations": limitations,
    }


def benchmark_generated_candidate(
    spec: WorkloadSpec,
    candidate: CandidateResult,
    *,
    record_count: int | None = None,
    operations: int = 2000,
    repetitions: int = 5,
    warmup: int = 1,
    compile_timeout_seconds: int = 90,
    run_timeout_seconds: int = 120,
) -> CandidateBenchmarkResult:
    if record_count is not None and record_count < 1:
        raise ValueError("record_count override must be positive")
    if operations < 1 or repetitions < 1 or warmup < 0:
        raise ValueError("operations/repetitions must be positive and warmup non-negative")

    artifact = generate_verified_header(spec, candidate)
    artifact_manifest = build_artifact_provenance_manifest(spec, candidate, artifact)
    _workload_ir, workload_hash = lower_and_hash_workload_ir(spec)
    _configuration_ir, configuration_hash = lower_and_hash_configuration_ir(spec, candidate)
    driver = generate_candidate_benchmark_driver(spec, candidate, artifact)
    driver_hash = hashlib.sha256(driver.encode("utf-8")).hexdigest()
    n = record_count if record_count is not None else spec.record_count
    limitations = (
        "Synthetic records are deterministic schema-derived inputs, not a claim that they represent a production value distribution.",
        "Declared query-row distributions are deterministic and precomputed outside timed query sections; hotspot means the first configured fraction of stable row IDs, and Zipf is the finite rank distribution over stable row IDs.",
        "Memory/RSS, cold-cache behavior and per-operation tail latency are not measured by this harness yet.",
        "The harness runs in a local process without CPU affinity, governor, thermal or background-load control.",
        "Graph routes use a deterministic chain topology unless a future topology-specific benchmark supplies another graph.",
    )
    base = _result_base(
        spec,
        candidate,
        artifact_manifest,
        driver_hash,
        workload_hash,
        configuration_hash,
        n=n,
        operations=operations,
        repetitions=repetitions,
        warmup=warmup,
        limitations=limitations,
    )

    toolchain = discover_toolchain()
    if toolchain is None:
        return CandidateBenchmarkResult(
            success=False,
            evidence_state="COMPILER_UNAVAILABLE",
            compiler=None,
            compiler_kind=None,
            compiler_version=None,
            compile_returncode=None,
            run_returncode=None,
            measurements=(),
            checksum=None,
            **base,
        )

    with tempfile.TemporaryDirectory(prefix="morpheus-candidate-bench-") as temporary:
        directory = Path(temporary)
        header_path = directory / artifact.header_name
        source_path = directory / "candidate_benchmark.cpp"
        binary_path = directory / ("candidate_benchmark.exe" if toolchain.kind == "msvc" else "candidate_benchmark")
        header_path.write_text(artifact.header_source, encoding="utf-8")
        source_path.write_text(driver, encoding="utf-8")
        command = compile_command(
            toolchain,
            source=source_path,
            output=binary_path,
            include_dirs=[CORE_INCLUDE, directory],
            optimize=True,
        )
        environment = base_environment(directory)

        try:
            compiled = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=compile_timeout_seconds,
                env=environment,
                cwd=directory,
                shell=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return CandidateBenchmarkResult(
                success=False,
                evidence_state="CANDIDATE_BENCHMARK_COMPILE_EXECUTION_ERROR",
                compiler=toolchain.executable,
                compiler_kind=toolchain.kind,
                compiler_version=toolchain.version,
                compile_returncode=None,
                run_returncode=None,
                measurements=(),
                checksum=None,
                compile_stderr=str(exc),
                **base,
            )

        if compiled.returncode != 0:
            return CandidateBenchmarkResult(
                success=False,
                evidence_state="CANDIDATE_BENCHMARK_COMPILE_FAILED",
                compiler=toolchain.executable,
                compiler_kind=toolchain.kind,
                compiler_version=toolchain.version,
                compile_returncode=compiled.returncode,
                run_returncode=None,
                measurements=(),
                checksum=None,
                compile_stdout=compiled.stdout[-8000:],
                compile_stderr=compiled.stderr[-8000:],
                **base,
            )

        try:
            executed = subprocess.run(
                [
                    str(binary_path),
                    "--n",
                    str(n),
                    "--ops",
                    str(operations),
                    "--repetitions",
                    str(repetitions),
                    "--warmup",
                    str(warmup),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=run_timeout_seconds,
                env=environment,
                cwd=directory,
                shell=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return CandidateBenchmarkResult(
                success=False,
                evidence_state="CANDIDATE_BENCHMARK_RUN_EXECUTION_ERROR",
                compiler=toolchain.executable,
                compiler_kind=toolchain.kind,
                compiler_version=toolchain.version,
                compile_returncode=compiled.returncode,
                run_returncode=None,
                measurements=(),
                checksum=None,
                compile_stdout=compiled.stdout[-8000:],
                compile_stderr=compiled.stderr[-8000:],
                run_stderr=str(exc),
                **base,
            )

        if executed.returncode != 0:
            return CandidateBenchmarkResult(
                success=False,
                evidence_state="CANDIDATE_BENCHMARK_RUN_FAILED",
                compiler=toolchain.executable,
                compiler_kind=toolchain.kind,
                compiler_version=toolchain.version,
                compile_returncode=compiled.returncode,
                run_returncode=executed.returncode,
                measurements=(),
                checksum=None,
                compile_stdout=compiled.stdout[-8000:],
                compile_stderr=compiled.stderr[-8000:],
                run_stdout=executed.stdout[-8000:],
                run_stderr=executed.stderr[-8000:],
                **base,
            )

        try:
            payload = json.loads(executed.stdout)
        except json.JSONDecodeError as exc:
            return CandidateBenchmarkResult(
                success=False,
                evidence_state="CANDIDATE_BENCHMARK_INVALID_OUTPUT",
                compiler=toolchain.executable,
                compiler_kind=toolchain.kind,
                compiler_version=toolchain.version,
                compile_returncode=compiled.returncode,
                run_returncode=executed.returncode,
                measurements=(),
                checksum=None,
                compile_stdout=compiled.stdout[-8000:],
                compile_stderr=compiled.stderr[-8000:],
                run_stdout=executed.stdout[-8000:],
                run_stderr=f"invalid JSON: {exc}; stderr={executed.stderr[-4000:]}",
                **base,
            )

        if (
            payload.get("candidate_id") != candidate.id
            or payload.get("distribution_protocol") != _DISTRIBUTION_PROTOCOL
            or not isinstance(payload.get("measurements"), list)
        ):
            return CandidateBenchmarkResult(
                success=False,
                evidence_state="CANDIDATE_BENCHMARK_PROVENANCE_MISMATCH",
                compiler=toolchain.executable,
                compiler_kind=toolchain.kind,
                compiler_version=toolchain.version,
                compile_returncode=compiled.returncode,
                run_returncode=executed.returncode,
                measurements=(),
                checksum=None,
                compile_stdout=compiled.stdout[-8000:],
                compile_stderr=compiled.stderr[-8000:],
                run_stdout=executed.stdout[-8000:],
                run_stderr="candidate benchmark output did not match requested candidate/distribution provenance",
                **base,
            )

        return CandidateBenchmarkResult(
            success=True,
            evidence_state=str(payload.get("evidence_state", "MEASURED_LOCAL_GENERATED_CANDIDATE_PROCESS")),
            compiler=toolchain.executable,
            compiler_kind=toolchain.kind,
            compiler_version=toolchain.version,
            compile_returncode=compiled.returncode,
            run_returncode=executed.returncode,
            measurements=tuple(dict(item) for item in payload["measurements"]),
            checksum=int(payload.get("checksum", 0)),
            compile_stdout=compiled.stdout[-8000:],
            compile_stderr=compiled.stderr[-8000:],
            run_stdout=executed.stdout[-8000:],
            run_stderr=executed.stderr[-8000:],
            **base,
        )
