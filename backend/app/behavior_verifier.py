from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .artifact_codegen import GeneratedArtifact
from .models import CandidateResult, QueryKind, WorkloadSpec
from .toolchain import base_environment, compile_command, discover_toolchain


@dataclass(frozen=True)
class BehaviorVerification:
    success: bool
    evidence_state: str
    compiler: str | None
    compiler_kind: str | None
    compiler_version: str | None
    source_sha256: str
    driver_sha256: str | None
    compile_returncode: int | None
    run_returncode: int | None
    compile_stdout: str
    compile_stderr: str
    run_stdout: str
    run_stderr: str
    checks: int
    command_policy: str
    limitations: list[str]

    def as_dict(self) -> dict[str, object]:
        return {
            "success": self.success,
            "evidence_state": self.evidence_state,
            "compiler": self.compiler,
            "compiler_kind": self.compiler_kind,
            "compiler_version": self.compiler_version,
            "source_sha256": self.source_sha256,
            "driver_sha256": self.driver_sha256,
            "compile_returncode": self.compile_returncode,
            "run_returncode": self.run_returncode,
            "compile_stdout": self.compile_stdout,
            "compile_stderr": self.compile_stderr,
            "run_stdout": self.run_stdout,
            "run_stderr": self.run_stderr,
            "checks": self.checks,
            "command_policy": self.command_policy,
            "limitations": self.limitations,
        }


def _normalized_type(raw: str) -> str:
    lowered = raw.lower()
    if lowered in {"uint64", "uint64_t", "uint32", "uint32_t", "int", "integer"}:
        return "integer"
    if lowered in {"float", "double"}:
        return "floating"
    if lowered == "bool":
        return "bool"
    return "string"


def _value(raw_type: str, field_index: int, row: int) -> object:
    kind = _normalized_type(raw_type)
    if kind == "integer":
        return row * 100 + field_index + 1
    if kind == "floating":
        return row * 10.0 + field_index + 0.25
    if kind == "bool":
        return bool((row + field_index) % 2)
    return f"f{field_index}_value_{row:03d}"


def _cpp_literal(raw_type: str, value: object) -> str:
    kind = _normalized_type(raw_type)
    if kind == "integer":
        return str(int(value))
    if kind == "floating":
        return f"{float(value):.6f}"
    if kind == "bool":
        return "true" if bool(value) else "false"
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'std::string("{escaped}")'


def _field(spec: WorkloadSpec, name: str):
    for field in spec.fields:
        if field.name == name:
            return field
    raise ValueError(f"unknown field in behavioral verifier: {name}")


def _record_literal(spec: WorkloadSpec, row: int) -> str:
    values = [_cpp_literal(field.type, _value(field.type, index, row)) for index, field in enumerate(spec.fields)]
    return "Record{" + ", ".join(values) + "}"


def _query_checks(spec: WorkloadSpec, candidate: CandidateResult) -> tuple[list[str], int]:
    blocks: list[str] = []
    checks = 0
    for assignment in candidate.assignments:
        if assignment.query_kind in {QueryKind.INSERT, QueryKind.UPDATE, QueryKind.DELETE}:
            continue
        if assignment.field is None:
            continue
        field = _field(spec, assignment.field)
        field_index = next(i for i, item in enumerate(spec.fields) if item.name == assignment.field)
        method = f"query_{assignment.query_index}"

        if assignment.query_kind == QueryKind.POINT_LOOKUP:
            target = _cpp_literal(field.type, _value(field.type, field_index, 2))
            block = f'''        {{
            const auto key = {target};
            auto actual = index.{method}(key);
            std::vector<Record> expected;
            for (const auto& record : reference) if (record.{field.name} == key) expected = {{record}};
            assert_same_multiset(actual, expected);
        }}'''
        elif assignment.query_kind == QueryKind.RANGE_SCAN:
            low = _cpp_literal(field.type, _value(field.type, field_index, 1))
            high = _cpp_literal(field.type, _value(field.type, field_index, 4))
            block = f'''        {{
            const auto low = {low};
            const auto high = {high};
            auto actual = index.{method}(low, high);
            std::vector<Record> expected;
            for (const auto& record : reference) {{
                if (!(record.{field.name} < low) && !(high < record.{field.name})) expected.push_back(record);
            }}
            assert_same_multiset(actual, expected);
        }}'''
        elif assignment.query_kind == QueryKind.FILTER:
            target = _cpp_literal(field.type, _value(field.type, field_index, 3))
            block = f'''        {{
            const auto key = {target};
            auto actual = index.{method}(key);
            std::vector<Record> expected;
            for (const auto& record : reference) if (record.{field.name} == key) expected.push_back(record);
            assert_same_multiset(actual, expected);
        }}'''
        elif assignment.query_kind == QueryKind.PREFIX_SEARCH:
            raw = str(_value(field.type, field_index, 2))
            prefix = raw[: max(1, min(4, len(raw)))]
            literal = _cpp_literal("string", prefix)
            block = f'''        {{
            const auto prefix = {literal};
            auto actual = index.{method}(prefix, 100);
            std::vector<Record> expected;
            for (const auto& record : reference) {{
                if (record.{field.name}.rfind(prefix, 0) == 0) expected.push_back(record);
            }}
            assert_same_multiset(actual, expected);
        }}'''
        else:
            continue
        blocks.append(block)
        checks += 1
    return blocks, checks


def generate_stateful_driver(spec: WorkloadSpec, candidate: CandidateResult, artifact: GeneratedArtifact) -> tuple[str, int]:
    query_blocks, query_count = _query_checks(spec, candidate)
    if query_count == 0:
        raise ValueError("behavioral verification requires at least one generated query route")

    initial_records = "\n".join(f"    insert({_record_literal(spec, row)});" for row in range(1, 7))
    update_one = _record_literal(spec, 20)
    update_two = _record_literal(spec, 30)
    query_text = "\n".join(query_blocks)
    state_checks = 4

    source = f'''#include "{artifact.header_name}"

#include <cassert>
#include <cstddef>
#include <string>
#include <vector>

int main() {{
    using Index = morpheus_generated::GeneratedIndex;
    using Record = Index::Record;

    Index index;
    std::vector<Record> reference;

    auto assert_same_multiset = [](const std::vector<Record>& actual, const std::vector<Record>& expected) {{
        assert(actual.size() == expected.size());
        std::vector<bool> matched(expected.size(), false);
        for (const auto& item : actual) {{
            bool found = false;
            for (std::size_t i = 0; i < expected.size(); ++i) {{
                if (!matched[i] && item == expected[i]) {{
                    matched[i] = true;
                    found = true;
                    break;
                }}
            }}
            assert(found);
        }}
    }};

    auto insert = [&](const Record& record) {{
        reference.push_back(record);
        index.insert(record);
    }};
    auto update = [&](std::size_t position, const Record& record) {{
        reference.at(position) = record;
        index.update_at(position, record);
    }};
    auto erase = [&](std::size_t position) {{
        reference.erase(reference.begin() + static_cast<std::ptrdiff_t>(position));
        index.erase_at(position);
    }};
    auto verify = [&]() {{
        assert(index.records() == reference);
{query_text}
    }};

{initial_records}
    verify();

    update(1, {update_one});
    verify();

    erase(0);
    verify();

    insert({update_two});
    verify();
    return 0;
}}
'''
    return source, query_count * state_checks + state_checks


def verify_generated_artifact_behavior(
    spec: WorkloadSpec,
    candidate: CandidateResult,
    artifact: GeneratedArtifact,
    *,
    compile_timeout_seconds: int = 60,
    run_timeout_seconds: int = 30,
) -> BehaviorVerification:
    source_sha = hashlib.sha256(artifact.header_source.encode("utf-8")).hexdigest()
    limitations = [
        "The gate uses deterministic schema-derived records and state transitions; it is not coverage-guided fuzzing.",
        "The gate validates generated query/mutation semantics against an independent reference vector, not concurrency or performance.",
        "Compilation and execution occur in a local process, not a hardened sandbox.",
    ]
    toolchain = discover_toolchain()
    if toolchain is None:
        return BehaviorVerification(
            False,
            "COMPILER_UNAVAILABLE",
            None,
            None,
            None,
            source_sha,
            None,
            None,
            None,
            "",
            "No supported C++20 compiler was found on PATH.",
            "",
            "",
            0,
            "FIXED_ARGUMENT_VECTOR_NO_SHELL",
            limitations,
        )

    try:
        driver_source, checks = generate_stateful_driver(spec, candidate, artifact)
    except ValueError as exc:
        return BehaviorVerification(
            False,
            "BEHAVIOR_DRIVER_UNAVAILABLE",
            toolchain.executable,
            toolchain.kind,
            toolchain.version,
            source_sha,
            None,
            None,
            None,
            "",
            str(exc),
            "",
            "",
            0,
            "FIXED_ARGUMENT_VECTOR_NO_SHELL",
            limitations,
        )
    driver_sha = hashlib.sha256(driver_source.encode("utf-8")).hexdigest()
    repo_root = Path(__file__).resolve().parents[2]
    core_include = (repo_root / "core" / "include").resolve()

    with tempfile.TemporaryDirectory(prefix="morpheus-behavior-") as raw_directory:
        directory = Path(raw_directory)
        header_path = directory / artifact.header_name
        driver_path = directory / "stateful_differential.cpp"
        binary_path = directory / ("stateful_differential.exe" if os.name == "nt" or toolchain.kind == "msvc" else "stateful_differential")
        header_path.write_text(artifact.header_source, encoding="utf-8")
        driver_path.write_text(driver_source, encoding="utf-8")
        environment = base_environment(raw_directory)
        command = compile_command(
            toolchain,
            source=driver_path,
            output=binary_path,
            include_dirs=[core_include, directory],
            optimize=False,
        )
        try:
            compile_process = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=compile_timeout_seconds,
                cwd=directory,
                env=environment,
            )
        except subprocess.TimeoutExpired:
            return BehaviorVerification(
                False,
                "BEHAVIOR_COMPILE_TIMEOUT",
                toolchain.executable,
                toolchain.kind,
                toolchain.version,
                source_sha,
                driver_sha,
                None,
                None,
                "",
                "Behavioral driver compilation exceeded the fixed timeout.",
                "",
                "",
                checks,
                "FIXED_ARGUMENT_VECTOR_NO_SHELL",
                limitations,
            )
        except OSError as exc:
            return BehaviorVerification(
                False,
                "BEHAVIOR_COMPILE_EXECUTION_ERROR",
                toolchain.executable,
                toolchain.kind,
                toolchain.version,
                source_sha,
                driver_sha,
                None,
                None,
                "",
                str(exc)[:8000],
                "",
                "",
                checks,
                "FIXED_ARGUMENT_VECTOR_NO_SHELL",
                limitations,
            )

        if compile_process.returncode != 0 or not binary_path.is_file():
            return BehaviorVerification(
                False,
                "BEHAVIOR_COMPILE_FAILED",
                toolchain.executable,
                toolchain.kind,
                toolchain.version,
                source_sha,
                driver_sha,
                compile_process.returncode,
                None,
                compile_process.stdout[:8000],
                compile_process.stderr[:8000],
                "",
                "",
                checks,
                "FIXED_ARGUMENT_VECTOR_NO_SHELL",
                limitations,
            )

        try:
            run_process = subprocess.run(
                [str(binary_path)],
                check=False,
                capture_output=True,
                text=True,
                timeout=run_timeout_seconds,
                cwd=directory,
                env=environment,
            )
        except subprocess.TimeoutExpired:
            return BehaviorVerification(
                False,
                "BEHAVIOR_RUN_TIMEOUT",
                toolchain.executable,
                toolchain.kind,
                toolchain.version,
                source_sha,
                driver_sha,
                compile_process.returncode,
                None,
                compile_process.stdout[:8000],
                compile_process.stderr[:8000],
                "",
                "Behavioral differential executable exceeded the fixed timeout.",
                checks,
                "FIXED_ARGUMENT_VECTOR_NO_SHELL",
                limitations,
            )
        except OSError as exc:
            return BehaviorVerification(
                False,
                "BEHAVIOR_RUN_EXECUTION_ERROR",
                toolchain.executable,
                toolchain.kind,
                toolchain.version,
                source_sha,
                driver_sha,
                compile_process.returncode,
                None,
                compile_process.stdout[:8000],
                compile_process.stderr[:8000],
                "",
                str(exc)[:8000],
                checks,
                "FIXED_ARGUMENT_VECTOR_NO_SHELL",
                limitations,
            )

        success = run_process.returncode == 0
        return BehaviorVerification(
            success,
            "STATEFUL_DIFFERENTIAL_VERIFIED_LOCAL_TOOLCHAIN" if success else "STATEFUL_DIFFERENTIAL_FAILED",
            toolchain.executable,
            toolchain.kind,
            toolchain.version,
            source_sha,
            driver_sha,
            compile_process.returncode,
            run_process.returncode,
            compile_process.stdout[:8000],
            compile_process.stderr[:8000],
            run_process.stdout[:8000],
            run_process.stderr[:8000],
            checks,
            "FIXED_ARGUMENT_VECTOR_NO_SHELL",
            limitations,
        )
