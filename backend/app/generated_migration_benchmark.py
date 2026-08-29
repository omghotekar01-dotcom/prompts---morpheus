from __future__ import annotations

import csv
import hashlib
import io
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .artifact_manifest import artifact_manifest_hash
from .generated_migration_bundle import (
    GeneratedMigrationBundle,
    _record_assignment_lines,
    _target_record_expression,
)
from .toolchain import base_environment, compile_command, discover_toolchain


REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_INCLUDE = REPO_ROOT / "core" / "include"
BENCHMARK_SCHEMA = "morpheus-generated-migration-benchmark-v1"
BENCHMARK_PROTOCOL = "morpheus-generated-migration-transition-cost-v1"


@dataclass(frozen=True)
class MigrationBenchmarkConfig:
    readers: int = 4
    transitions: int = 25
    repetitions: int = 3
    record_count: int = 1024

    def validate(self) -> None:
        if not 1 <= self.readers <= 128:
            raise ValueError("readers must be in [1, 128]")
        if not 1 <= self.transitions <= 10_000:
            raise ValueError("transitions must be in [1, 10000]")
        if not 1 <= self.repetitions <= 1_000:
            raise ValueError("repetitions must be in [1, 1000]")
        if not 1 <= self.record_count <= 10_000_000:
            raise ValueError("record_count must be in [1, 10000000]")


@dataclass(frozen=True)
class MigrationBenchmarkRow:
    repetition: int
    readers: int
    transitions: int
    record_count: int
    migrate_validate_activate_ns_per: int
    rollback_ns_per: int
    reads: int
    invalid_reads: int

    def as_dict(self) -> dict[str, int]:
        return {
            "repetition": self.repetition,
            "readers": self.readers,
            "transitions": self.transitions,
            "record_count": self.record_count,
            "migrate_validate_activate_ns_per": self.migrate_validate_activate_ns_per,
            "rollback_ns_per": self.rollback_ns_per,
            "reads": self.reads,
            "invalid_reads": self.invalid_reads,
        }


@dataclass(frozen=True)
class GeneratedMigrationBenchmarkReport:
    success: bool
    evidence_state: str
    source_candidate_id: str
    target_candidate_id: str
    workload_ir_hash: str
    source_configuration_ir_hash: str
    target_configuration_ir_hash: str
    source_manifest_sha256: str
    target_manifest_sha256: str
    source_header_sha256: str
    target_header_sha256: str
    benchmark_source_sha256: str
    compiler: str | None
    compiler_kind: str | None
    compiler_version: str | None
    config: MigrationBenchmarkConfig
    rows: tuple[MigrationBenchmarkRow, ...]
    compile_returncode: int | None
    run_returncode: int | None
    compile_stdout: str = ""
    compile_stderr: str = ""
    run_stdout: str = ""
    run_stderr: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": BENCHMARK_SCHEMA,
            "protocol": BENCHMARK_PROTOCOL,
            "success": self.success,
            "evidence_state": self.evidence_state,
            "source_candidate_id": self.source_candidate_id,
            "target_candidate_id": self.target_candidate_id,
            "workload_ir_hash": self.workload_ir_hash,
            "source_configuration_ir_hash": self.source_configuration_ir_hash,
            "target_configuration_ir_hash": self.target_configuration_ir_hash,
            "source_manifest_sha256": self.source_manifest_sha256,
            "target_manifest_sha256": self.target_manifest_sha256,
            "source_header_sha256": self.source_header_sha256,
            "target_header_sha256": self.target_header_sha256,
            "benchmark_source_sha256": self.benchmark_source_sha256,
            "compiler": self.compiler,
            "compiler_kind": self.compiler_kind,
            "compiler_version": self.compiler_version,
            "config": {
                "readers": self.config.readers,
                "transitions": self.config.transitions,
                "repetitions": self.config.repetitions,
                "record_count": self.config.record_count,
            },
            "rows": [row.as_dict() for row in self.rows],
            "compile_returncode": self.compile_returncode,
            "run_returncode": self.run_returncode,
            "compile_stdout": self.compile_stdout,
            "compile_stderr": self.compile_stderr,
            "run_stdout": self.run_stdout,
            "run_stderr": self.run_stderr,
            "truth_boundary": (
                "Rows are local wall-clock measurements of generated same-process migration+shadow-validation+publication "
                "and rollback under the declared compiler/configuration. They are not universal performance evidence. "
                "GitHub Actions executions are smoke measurements and must not be promoted to publication-grade results."
            ),
        }


def build_generated_migration_benchmark_source(bundle: GeneratedMigrationBundle, spec) -> str:
    assignments = _record_assignment_lines(spec)
    converted_record = _target_record_expression(spec, "record")
    converted_row = _target_record_expression(spec, "source_rows[i]")
    template = r'''#include "__SOURCE_HEADER__"
#include "__TARGET_HEADER__"
#include "morpheus/migration_publish.hpp"

#include <atomic>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <thread>
#include <typeindex>
#include <typeinfo>
#include <vector>

using Source = __SOURCE_NAMESPACE__::GeneratedIndex;
using Target = __TARGET_NAMESPACE__::GeneratedIndex;
using Version = morpheus::ErasedVersionedSlot::Version;

struct Options {
    std::size_t readers = 4;
    std::size_t transitions = 25;
    std::size_t repetitions = 3;
    std::size_t record_count = 1024;
};

std::size_t parse_size(const char* text, const char* name) {
    try {
        const auto value = std::stoull(text);
        if (value == 0) throw std::invalid_argument("zero");
        return static_cast<std::size_t>(value);
    } catch (...) {
        throw std::invalid_argument(std::string("invalid value for ") + name);
    }
}

Options parse_args(int argc, char** argv) {
    Options options;
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        auto require_value = [&](const char* name) -> const char* {
            if (i + 1 >= argc) throw std::invalid_argument(std::string("missing value for ") + name);
            return argv[++i];
        };
        if (arg == "--readers") options.readers = parse_size(require_value("--readers"), "--readers");
        else if (arg == "--transitions") options.transitions = parse_size(require_value("--transitions"), "--transitions");
        else if (arg == "--repetitions") options.repetitions = parse_size(require_value("--repetitions"), "--repetitions");
        else if (arg == "--record-count") options.record_count = parse_size(require_value("--record-count"), "--record-count");
        else throw std::invalid_argument("unknown argument: " + arg);
    }
    return options;
}

template <typename Payload>
std::shared_ptr<const Payload> payload_as(const std::shared_ptr<const Version>& version) {
    if (!version || version->payload_type != std::type_index(typeid(Payload))) return {};
    return std::shared_ptr<const Payload>(version->payload, static_cast<const Payload*>(version->payload.get()));
}

Target::Record convert_record(const Source::Record& record) {
    return __CONVERTED_RECORD__;
}

bool same_logical_state(const Source& source, const Target& target) {
    const auto& source_rows = source.records();
    const auto& target_rows = target.records();
    if (source_rows.size() != target_rows.size()) return false;
    for (std::size_t i = 0; i < source_rows.size(); ++i) {
        const auto converted = __CONVERTED_ROW__;
        if (!(target_rows[i] == converted)) return false;
    }
    return true;
}

std::shared_ptr<const Source> make_source(std::size_t record_count) {
    auto source = std::make_shared<Source>();
    for (std::size_t i = 0; i < record_count; ++i) {
        Source::Record record{};
__RECORD_ASSIGNMENTS__
        source->insert(record);
    }
    (void)source->records();
    return source;
}

int main(int argc, char** argv) {
    try {
        using Clock = std::chrono::steady_clock;
        const auto options = parse_args(argc, argv);
        std::cout << "repetition,readers,transitions,record_count,migrate_validate_activate_ns_per,rollback_ns_per,reads,invalid_reads\n";

        for (std::size_t repetition = 0; repetition < options.repetitions; ++repetition) {
            auto source = make_source(options.record_count);
            morpheus::ErasedVersionedSlot slot("__SOURCE_CANDIDATE__", source);
            std::atomic<bool> stop{false};
            std::atomic<std::uint64_t> reads{0};
            std::atomic<std::uint64_t> invalid{0};
            std::vector<std::thread> reader_threads;
            reader_threads.reserve(options.readers);
            for (std::size_t reader = 0; reader < options.readers; ++reader) {
                reader_threads.emplace_back([&] {
                    while (!stop.load(std::memory_order_relaxed)) {
                        const auto version = slot.lease();
                        if (!version) { ++invalid; continue; }
                        if (version->payload_type == std::type_index(typeid(Source))) {
                            const auto typed = payload_as<Source>(version);
                            if (!typed || version->candidate_id != "__SOURCE_CANDIDATE__" || typed->size() != options.record_count) ++invalid;
                        } else if (version->payload_type == std::type_index(typeid(Target))) {
                            const auto typed = payload_as<Target>(version);
                            if (!typed || version->candidate_id != "__TARGET_CANDIDATE__" || typed->size() != options.record_count) ++invalid;
                        } else {
                            ++invalid;
                        }
                        ++reads;
                    }
                });
            }

            std::uint64_t migrate_ns = 0;
            std::uint64_t rollback_ns = 0;
            for (std::size_t transition = 0; transition < options.transitions; ++transition) {
                const auto source_version = slot.lease();
                if (source_version->candidate_id != "__SOURCE_CANDIDATE__") throw std::runtime_error("expected source candidate");
                const auto active_source = payload_as<Source>(source_version);
                if (!active_source) throw std::runtime_error("source payload type mismatch");

                const auto migrate_start = Clock::now();
                (void)morpheus::migrate_validate_and_activate<Source, Target>(
                    slot,
                    source_version,
                    "__TARGET_CANDIDATE__",
                    *active_source,
                    convert_record,
                    [&](const Target& target) { return same_logical_state(*active_source, target); }
                );
                const auto migrate_end = Clock::now();
                migrate_ns += static_cast<std::uint64_t>(
                    std::chrono::duration_cast<std::chrono::nanoseconds>(migrate_end - migrate_start).count()
                );

                const auto target_version = slot.lease();
                if (target_version->candidate_id != "__TARGET_CANDIDATE__") throw std::runtime_error("expected target candidate");
                const auto rollback_start = Clock::now();
                (void)slot.rollback(target_version);
                const auto rollback_end = Clock::now();
                rollback_ns += static_cast<std::uint64_t>(
                    std::chrono::duration_cast<std::chrono::nanoseconds>(rollback_end - rollback_start).count()
                );
            }

            stop.store(true, std::memory_order_relaxed);
            for (auto& thread : reader_threads) thread.join();
            if (invalid.load() != 0) return 2;
            std::cout << repetition << ',' << options.readers << ',' << options.transitions << ',' << options.record_count << ','
                      << (migrate_ns / options.transitions) << ',' << (rollback_ns / options.transitions) << ','
                      << reads.load() << ',' << invalid.load() << '\n';
        }
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
'''
    replacements = {
        "__SOURCE_HEADER__": bundle.source_artifact.header_name,
        "__TARGET_HEADER__": bundle.target_artifact.header_name,
        "__SOURCE_NAMESPACE__": bundle.source_artifact.namespace_name,
        "__TARGET_NAMESPACE__": bundle.target_artifact.namespace_name,
        "__SOURCE_CANDIDATE__": bundle.source_candidate_id,
        "__TARGET_CANDIDATE__": bundle.target_candidate_id,
        "__CONVERTED_RECORD__": converted_record,
        "__CONVERTED_ROW__": converted_row,
        "__RECORD_ASSIGNMENTS__": assignments,
    }
    for marker, value in replacements.items():
        template = template.replace(marker, value)
    return template


def _bounded(text: str | None, limit: int = 16_000) -> str:
    return (text or "")[-limit:]


def _report_base(bundle: GeneratedMigrationBundle, source_sha: str) -> dict[str, Any]:
    return {
        "source_candidate_id": bundle.source_candidate_id,
        "target_candidate_id": bundle.target_candidate_id,
        "workload_ir_hash": bundle.source_manifest.workload_ir_hash,
        "source_configuration_ir_hash": bundle.source_manifest.configuration_ir_hash,
        "target_configuration_ir_hash": bundle.target_manifest.configuration_ir_hash,
        "source_manifest_sha256": artifact_manifest_hash(bundle.source_manifest),
        "target_manifest_sha256": artifact_manifest_hash(bundle.target_manifest),
        "source_header_sha256": bundle.source_manifest.source_sha256,
        "target_header_sha256": bundle.target_manifest.source_sha256,
        "benchmark_source_sha256": source_sha,
    }


def _parse_rows(stdout: str, config: MigrationBenchmarkConfig) -> tuple[MigrationBenchmarkRow, ...]:
    reader = csv.DictReader(io.StringIO(stdout))
    expected = [
        "repetition",
        "readers",
        "transitions",
        "record_count",
        "migrate_validate_activate_ns_per",
        "rollback_ns_per",
        "reads",
        "invalid_reads",
    ]
    if reader.fieldnames != expected:
        raise ValueError("generated migration benchmark emitted an unexpected CSV schema")
    rows: list[MigrationBenchmarkRow] = []
    for raw in reader:
        row = MigrationBenchmarkRow(**{key: int(raw[key]) for key in expected})
        if row.readers != config.readers or row.transitions != config.transitions or row.record_count != config.record_count:
            raise ValueError("benchmark row does not match requested configuration")
        if row.migrate_validate_activate_ns_per < 0 or row.rollback_ns_per < 0 or row.reads <= 0 or row.invalid_reads != 0:
            raise ValueError("benchmark row failed timing/reader invariants")
        rows.append(row)
    if len(rows) != config.repetitions:
        raise ValueError("benchmark emitted an unexpected repetition count")
    if [row.repetition for row in rows] != list(range(config.repetitions)):
        raise ValueError("benchmark repetition ids are not contiguous")
    return tuple(rows)


def benchmark_generated_migration_bundle(
    bundle: GeneratedMigrationBundle,
    spec,
    *,
    config: MigrationBenchmarkConfig = MigrationBenchmarkConfig(),
    compile_timeout_seconds: int = 120,
    run_timeout_seconds: int = 120,
) -> GeneratedMigrationBenchmarkReport:
    config.validate()
    if not 1 <= compile_timeout_seconds <= 600 or not 1 <= run_timeout_seconds <= 600:
        raise ValueError("benchmark timeouts must be in [1, 600]")
    benchmark_source = build_generated_migration_benchmark_source(bundle, spec)
    source_sha = hashlib.sha256(benchmark_source.encode("utf-8")).hexdigest()
    base = _report_base(bundle, source_sha)
    toolchain = discover_toolchain()
    if toolchain is None:
        return GeneratedMigrationBenchmarkReport(
            success=False,
            evidence_state="COMPILER_UNAVAILABLE",
            compiler=None,
            compiler_kind=None,
            compiler_version=None,
            config=config,
            rows=(),
            compile_returncode=None,
            run_returncode=None,
            **base,
        )

    with tempfile.TemporaryDirectory(prefix="morpheus-generated-migration-bench-") as temporary:
        directory = Path(temporary).resolve()
        (directory / bundle.source_artifact.header_name).write_text(bundle.source_artifact.header_source, encoding="utf-8")
        (directory / bundle.target_artifact.header_name).write_text(bundle.target_artifact.header_source, encoding="utf-8")
        source_path = directory / "generated_migration_benchmark.cpp"
        source_path.write_text(benchmark_source, encoding="utf-8")
        binary_path = directory / ("generated_migration_benchmark.exe" if toolchain.kind == "msvc" else "generated_migration_benchmark")
        command = compile_command(toolchain, source=source_path, output=binary_path, include_dirs=[CORE_INCLUDE, directory], optimize=True)
        if toolchain.kind != "msvc":
            command.append("-pthread")
        environment = base_environment(directory)
        try:
            compiled = subprocess.run(command, cwd=directory, env=environment, shell=False, capture_output=True, text=True, timeout=compile_timeout_seconds, check=False)
        except subprocess.TimeoutExpired:
            return GeneratedMigrationBenchmarkReport(False, "GENERATED_MIGRATION_BENCHMARK_COMPILE_TIMED_OUT", compiler=toolchain.executable, compiler_kind=toolchain.kind, compiler_version=toolchain.version, config=config, rows=(), compile_returncode=None, run_returncode=None, **base)
        compile_stdout = _bounded(compiled.stdout); compile_stderr = _bounded(compiled.stderr)
        if compiled.returncode != 0 or not binary_path.exists():
            return GeneratedMigrationBenchmarkReport(False, "GENERATED_MIGRATION_BENCHMARK_COMPILE_FAILED", compiler=toolchain.executable, compiler_kind=toolchain.kind, compiler_version=toolchain.version, config=config, rows=(), compile_returncode=compiled.returncode, run_returncode=None, compile_stdout=compile_stdout, compile_stderr=compile_stderr, **base)

        run_command = [str(binary_path), "--readers", str(config.readers), "--transitions", str(config.transitions), "--repetitions", str(config.repetitions), "--record-count", str(config.record_count)]
        try:
            executed = subprocess.run(run_command, cwd=directory, env=environment, shell=False, capture_output=True, text=True, timeout=run_timeout_seconds, check=False)
        except subprocess.TimeoutExpired:
            return GeneratedMigrationBenchmarkReport(False, "GENERATED_MIGRATION_BENCHMARK_RUN_TIMED_OUT", compiler=toolchain.executable, compiler_kind=toolchain.kind, compiler_version=toolchain.version, config=config, rows=(), compile_returncode=compiled.returncode, run_returncode=None, compile_stdout=compile_stdout, compile_stderr=compile_stderr, **base)
        run_stdout = _bounded(executed.stdout); run_stderr = _bounded(executed.stderr)
        if executed.returncode != 0:
            return GeneratedMigrationBenchmarkReport(False, "GENERATED_MIGRATION_BENCHMARK_RUN_FAILED", compiler=toolchain.executable, compiler_kind=toolchain.kind, compiler_version=toolchain.version, config=config, rows=(), compile_returncode=compiled.returncode, run_returncode=executed.returncode, compile_stdout=compile_stdout, compile_stderr=compile_stderr, run_stdout=run_stdout, run_stderr=run_stderr, **base)
        try:
            rows = _parse_rows(executed.stdout, config)
        except (TypeError, ValueError) as exc:
            return GeneratedMigrationBenchmarkReport(False, "GENERATED_MIGRATION_BENCHMARK_OUTPUT_INVALID", compiler=toolchain.executable, compiler_kind=toolchain.kind, compiler_version=toolchain.version, config=config, rows=(), compile_returncode=compiled.returncode, run_returncode=executed.returncode, compile_stdout=compile_stdout, compile_stderr=compile_stderr, run_stdout=run_stdout, run_stderr=str(exc), **base)

        state = "MEASURED_CI_SMOKE_GENERATED_MIGRATION_TRANSITION_COST" if os.environ.get("GITHUB_ACTIONS") == "true" else "MEASURED_LOCAL_PROCESS_GENERATED_MIGRATION_TRANSITION_COST"
        return GeneratedMigrationBenchmarkReport(True, state, compiler=toolchain.executable, compiler_kind=toolchain.kind, compiler_version=toolchain.version, config=config, rows=rows, compile_returncode=compiled.returncode, run_returncode=executed.returncode, compile_stdout=compile_stdout, compile_stderr=compile_stderr, run_stdout=run_stdout, run_stderr=run_stderr, **base)
