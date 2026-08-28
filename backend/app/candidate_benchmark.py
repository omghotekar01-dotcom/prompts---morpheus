from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .artifact_codegen import GeneratedArtifact, generate_verified_header
from .artifact_manifest import build_artifact_provenance_manifest
from .configuration_ir import lower_and_hash_configuration_ir
from .models import CandidateResult, QueryKind, WorkloadSpec
from .parser import semantic_hash
from .toolchain import base_environment, compile_command, discover_toolchain
from .workload_ir import lower_and_hash_workload_ir


REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_INCLUDE = REPO_ROOT / "core" / "include"


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
            "compile_stdout": self.compile_stdout,
            "compile_stderr": self.compile_stderr,
            "run_stdout": self.run_stdout,
            "run_stderr": self.run_stderr,
            "limitations": list(self.limitations),
            "truth_boundary": (
                "Successful output is a repeated local-process measurement of one generated candidate on the discovered toolchain. "
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
    domain_expr = "row"
    if cardinality is not None:
        domain_expr = f"(row % {max(1, cardinality)})"
    kind = _normalized_type(raw_type)
    cpp_type = _cpp_type(raw_type)
    if kind == "integer":
        return f"static_cast<{cpp_type}>(({domain_expr}) * 100ULL + {field_index + 1}ULL)"
    if kind == "floating":
        return f"static_cast<double>(({domain_expr}) * 10.0 + {field_index}.25)"
    if kind == "bool":
        return f"static_cast<bool>(({domain_expr} + {field_index}) % 2)"
    return f'field_string({field_index}, static_cast<std::uint64_t>({domain_expr}))'


def _record_factory(spec: WorkloadSpec) -> str:
    expressions = [
        _field_expression(field.type, index, field.cardinality)
        for index, field in enumerate(spec.fields)
    ]
    return "    return Record{" + ", ".join(expressions) + "};"


def _route_block(spec: WorkloadSpec, assignment, operations_name: str = "operations") -> str:
    method = f"query_{assignment.query_index}"
    kind = assignment.query_kind
    if kind == QueryKind.GRAPH_TRAVERSAL:
        return f'''        measurements.push_back(measure("query_{assignment.query_index}", "graph_traversal", {operations_name}, repetitions, warmup, [&](std::size_t rep) {{
            for (std::size_t i = 0; i < {operations_name}; ++i) {{
                const auto start = static_cast<std::uint32_t>(query_row(i + rep, n));
                checksum += index.{method}(start, 4).size();
            }}
        }}));'''
    if assignment.field is None:
        raise ValueError(f"candidate route {assignment.query_index} lacks a field")
    field_name = assignment.field
    query = spec.queries[assignment.query_index]
    if kind == QueryKind.POINT_LOOKUP:
        body = f'''const auto record = make_record(query_row(i + rep, n));
                checksum += index.{method}(record.{field_name}).size();'''
    elif kind == QueryKind.FILTER:
        body = f'''const auto record = make_record(query_row(i + rep, n));
                checksum += index.{method}(record.{field_name}).size();'''
    elif kind == QueryKind.RANGE_SCAN:
        body = f'''auto low = make_record(query_row(i + rep, n)).{field_name};
                auto high = make_record(query_row(i + rep + 7, n)).{field_name};
                if (high < low) std::swap(low, high);
                checksum += index.{method}(low, high).size();'''
    elif kind == QueryKind.PREFIX_SEARCH:
        prefix_length = max(1, query.prefix_length or 12)
        body = f'''const auto record = make_record(query_row(i + rep, n));
                const auto prefix = record.{field_name}.substr(0, std::min<std::size_t>({prefix_length}, record.{field_name}.size()));
                checksum += index.{method}(prefix, 64).size();'''
    else:
        raise ValueError(f"unsupported read route in candidate benchmark: {kind.value}")
    return f'''        measurements.push_back(measure("query_{assignment.query_index}", "{kind.value}", {operations_name}, repetitions, warmup, [&](std::size_t rep) {{
            for (std::size_t i = 0; i < {operations_name}; ++i) {{
                {body}
            }}
        }}));'''


def _graph_configuration_blocks(candidate: CandidateResult) -> str:
    blocks: list[str] = []
    for assignment in candidate.assignments:
        if assignment.query_kind == QueryKind.GRAPH_TRAVERSAL:
            blocks.append(
                f'''        index.configure_graph_{assignment.query_index}(n, make_chain_edges(n), true);'''
            )
    return "\n".join(blocks)


def generate_candidate_benchmark_driver(
    spec: WorkloadSpec,
    candidate: CandidateResult,
    artifact: GeneratedArtifact,
) -> str:
    read_assignments = [
        assignment
        for assignment in candidate.assignments
        if assignment.query_kind not in {QueryKind.INSERT, QueryKind.UPDATE, QueryKind.DELETE}
    ]
    if not read_assignments:
        raise ValueError("candidate benchmark requires at least one queryable route")
    route_blocks = "\n".join(_route_block(spec, assignment) for assignment in read_assignments)
    graph_configuration = _graph_configuration_blocks(candidate)
    has_record_backed_route = any(
        assignment.query_kind != QueryKind.GRAPH_TRAVERSAL for assignment in read_assignments
    )
    update_block = ""
    if has_record_backed_route:
        update_block = '''        measurements.push_back(measure("generated_candidate", "update_record", operations, repetitions, warmup, [&](std::size_t rep) {
            for (std::size_t i = 0; i < operations; ++i) {
                const auto position = query_row(i + rep, n);
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
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

using Index = morpheus_generated::GeneratedIndex;
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

std::string field_string(std::size_t field, std::uint64_t value) {{
    std::ostringstream stream;
    stream << 'f' << field << "_value_" << std::setw(12) << std::setfill('0') << value;
    return stream.str();
}}

Record make_record(std::size_t row) {{
{_record_factory(spec)}
}}

std::size_t query_row(std::size_t i, std::size_t n) {{
    if (n == 0) throw std::runtime_error("empty benchmark dataset");
    return static_cast<std::size_t>((static_cast<std::uint64_t>(i) * 11400714819323198485ULL + 0x9E3779B97F4A7C15ULL) % n);
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
        samples.push_back(std::chrono::duration<double, std::nano>(stop - start).count() / static_cast<double>(operations));
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
    return {{std::move(name), std::move(operation), median, mean, std::sqrt(variance), sorted.front(), sorted.back(), std::move(samples)}};
}}

void print_measurement(const Measurement& item) {{
    std::cout << "{{\"name\":\"" << item.name
              << "\",\"operation\":\"" << item.operation
              << "\",\"median_ns\":" << item.median_ns
              << ",\"mean_ns\":" << item.mean_ns
              << ",\"stdev_ns\":" << item.stdev_ns
              << ",\"min_ns\":" << item.min_ns
              << ",\"max_ns\":" << item.max_ns
              << ",\"samples_ns\":[";
    for (std::size_t i = 0; i < item.samples_ns.size(); ++i) {{
        if (i) std::cout << ',';
        std::cout << item.samples_ns[i];
    }}
    std::cout << "]}}";
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
        if (n == 0 || operations == 0 || repetitions == 0) throw std::runtime_error("n/ops/repetitions must be positive");
        if (n > 10000000 || operations > 10000000 || repetitions > 100 || warmup > 20) throw std::runtime_error("benchmark safety limit exceeded");
        if (n > static_cast<std::size_t>(std::numeric_limits<std::uint32_t>::max())) throw std::runtime_error("candidate benchmark exceeds generated compressed-bitmap slot domain");

        std::uint64_t checksum = 0;
        std::vector<Measurement> measurements;
        measurements.push_back(measure("generated_candidate", "build_end_to_end", n, repetitions, warmup, [&](std::size_t) {{
            Index candidate;
            for (std::size_t row = 0; row < n; ++row) candidate.insert(make_record(row));
{graph_configuration}
            checksum += candidate.size();
        }}));

        Index index;
        for (std::size_t row = 0; row < n; ++row) index.insert(make_record(row));
{graph_configuration}

{route_blocks}
{update_block}

        std::cout << std::fixed << std::setprecision(3);
        std::cout << "{{\"protocol\":\"morpheus-generated-candidate-benchmark-v1\","
                  << "\"evidence_state\":\"MEASURED_LOCAL_GENERATED_CANDIDATE_PROCESS\","
                  << "\"candidate_id\":\"{candidate.id}\","
                  << "\"record_count\":" << n << ','
                  << "\"operations\":" << operations << ','
                  << "\"repetitions\":" << repetitions << ','
                  << "\"warmup_repetitions\":" << warmup << ','
                  << "\"checksum\":" << checksum << ','
                  << "\"measurements\":[";
        for (std::size_t i = 0; i < measurements.size(); ++i) {{
            if (i) std::cout << ',';
            print_measurement(measurements[i]);
        }}
        std::cout << "]}}\n";
        return 0;
    }} catch (const std::exception& error) {{
        std::cerr << "morpheus candidate benchmark: " << error.what() << '\n';
        return 2;
    }}
}}
'''


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
    limitations = (
        "Synthetic values are deterministic schema-derived inputs, not a claim that they represent a production distribution.",
        "Memory/RSS and cold-cache behavior are not measured by this harness yet.",
        "The harness runs in a local process without CPU affinity, governor, thermal or background-load control.",
        "Graph routes use a deterministic chain topology unless a future topology-specific benchmark supplies another graph.",
    )
    toolchain = discover_toolchain()
    n = record_count if record_count is not None else spec.record_count
    if toolchain is None:
        return CandidateBenchmarkResult(
            False,
            "COMPILER_UNAVAILABLE",
            candidate.id,
            semantic_hash(spec),
            workload_hash,
            configuration_hash,
            artifact_manifest.primitive_manifest_hash,
            artifact_manifest.source_sha256,
            driver_hash,
            None,
            None,
            None,
            None,
            None,
            n,
            operations,
            repetitions,
            warmup,
            (),
            None,
            limitations=limitations,
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
                False,
                "CANDIDATE_BENCHMARK_COMPILE_EXECUTION_ERROR",
                candidate.id,
                semantic_hash(spec),
                workload_hash,
                configuration_hash,
                artifact_manifest.primitive_manifest_hash,
                artifact_manifest.source_sha256,
                driver_hash,
                toolchain.executable,
                toolchain.kind,
                toolchain.version,
                None,
                None,
                n,
                operations,
                repetitions,
                warmup,
                (),
                None,
                compile_stderr=str(exc),
                limitations=limitations,
            )
        if compiled.returncode != 0:
            return CandidateBenchmarkResult(
                False,
                "CANDIDATE_BENCHMARK_COMPILE_FAILED",
                candidate.id,
                semantic_hash(spec),
                workload_hash,
                configuration_hash,
                artifact_manifest.primitive_manifest_hash,
                artifact_manifest.source_sha256,
                driver_hash,
                toolchain.executable,
                toolchain.kind,
                toolchain.version,
                compiled.returncode,
                None,
                n,
                operations,
                repetitions,
                warmup,
                (),
                None,
                compile_stdout=compiled.stdout[-8000:],
                compile_stderr=compiled.stderr[-8000:],
                limitations=limitations,
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
                False,
                "CANDIDATE_BENCHMARK_RUN_EXECUTION_ERROR",
                candidate.id,
                semantic_hash(spec),
                workload_hash,
                configuration_hash,
                artifact_manifest.primitive_manifest_hash,
                artifact_manifest.source_sha256,
                driver_hash,
                toolchain.executable,
                toolchain.kind,
                toolchain.version,
                compiled.returncode,
                None,
                n,
                operations,
                repetitions,
                warmup,
                (),
                None,
                compile_stdout=compiled.stdout[-8000:],
                compile_stderr=compiled.stderr[-8000:],
                run_stderr=str(exc),
                limitations=limitations,
            )
        if executed.returncode != 0:
            return CandidateBenchmarkResult(
                False,
                "CANDIDATE_BENCHMARK_RUN_FAILED",
                candidate.id,
                semantic_hash(spec),
                workload_hash,
                configuration_hash,
                artifact_manifest.primitive_manifest_hash,
                artifact_manifest.source_sha256,
                driver_hash,
                toolchain.executable,
                toolchain.kind,
                toolchain.version,
                compiled.returncode,
                executed.returncode,
                n,
                operations,
                repetitions,
                warmup,
                (),
                None,
                compile_stdout=compiled.stdout[-8000:],
                compile_stderr=compiled.stderr[-8000:],
                run_stdout=executed.stdout[-8000:],
                run_stderr=executed.stderr[-8000:],
                limitations=limitations,
            )
        try:
            payload = json.loads(executed.stdout)
        except json.JSONDecodeError as exc:
            return CandidateBenchmarkResult(
                False,
                "CANDIDATE_BENCHMARK_INVALID_OUTPUT",
                candidate.id,
                semantic_hash(spec),
                workload_hash,
                configuration_hash,
                artifact_manifest.primitive_manifest_hash,
                artifact_manifest.source_sha256,
                driver_hash,
                toolchain.executable,
                toolchain.kind,
                toolchain.version,
                compiled.returncode,
                executed.returncode,
                n,
                operations,
                repetitions,
                warmup,
                (),
                None,
                compile_stdout=compiled.stdout[-8000:],
                compile_stderr=compiled.stderr[-8000:],
                run_stdout=executed.stdout[-8000:],
                run_stderr=f"invalid JSON: {exc}; stderr={executed.stderr[-4000:]}",
                limitations=limitations,
            )

        return CandidateBenchmarkResult(
            True,
            str(payload.get("evidence_state", "MEASURED_LOCAL_GENERATED_CANDIDATE_PROCESS")),
            candidate.id,
            semantic_hash(spec),
            workload_hash,
            configuration_hash,
            artifact_manifest.primitive_manifest_hash,
            artifact_manifest.source_sha256,
            driver_hash,
            toolchain.executable,
            toolchain.kind,
            toolchain.version,
            compiled.returncode,
            executed.returncode,
            int(payload.get("record_count", n)),
            int(payload.get("operations", operations)),
            int(payload.get("repetitions", repetitions)),
            int(payload.get("warmup_repetitions", warmup)),
            tuple(dict(item) for item in payload.get("measurements", [])),
            int(payload.get("checksum", 0)),
            compile_stdout=compiled.stdout[-8000:],
            compile_stderr=compiled.stderr[-8000:],
            run_stdout=executed.stdout[-8000:],
            run_stderr=executed.stderr[-8000:],
            limitations=limitations,
        )
