from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .artifact_manifest import artifact_manifest_hash
from .generated_migration_bundle import GeneratedMigrationBundle
from .toolchain import base_environment, compile_command, discover_toolchain


REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_INCLUDE = REPO_ROOT / "core" / "include"
VERIFICATION_SCHEMA = "morpheus-generated-migration-verification-v1"
_SUCCESS_MARKER = "MORPHEUS_GENERATED_MIGRATION_OK"
_COUNTER_PATTERN = re.compile(r"\b(source_reads|target_reads|invalid_reads|final_generation)=(\d+)\b")


@dataclass(frozen=True)
class GeneratedMigrationVerificationResult:
    success: bool
    evidence_state: str
    source_candidate_id: str
    target_candidate_id: str
    source_manifest_sha256: str
    target_manifest_sha256: str
    harness_sha256: str
    compiler: str | None
    compiler_kind: str | None
    compiler_version: str | None
    compile_returncode: int | None
    run_returncode: int | None
    source_reads: int | None = None
    target_reads: int | None = None
    invalid_reads: int | None = None
    final_generation: int | None = None
    compile_stdout: str = ""
    compile_stderr: str = ""
    run_stdout: str = ""
    run_stderr: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": VERIFICATION_SCHEMA,
            "success": self.success,
            "evidence_state": self.evidence_state,
            "source_candidate_id": self.source_candidate_id,
            "target_candidate_id": self.target_candidate_id,
            "source_manifest_sha256": self.source_manifest_sha256,
            "target_manifest_sha256": self.target_manifest_sha256,
            "harness_sha256": self.harness_sha256,
            "compiler": self.compiler,
            "compiler_kind": self.compiler_kind,
            "compiler_version": self.compiler_version,
            "compile_returncode": self.compile_returncode,
            "run_returncode": self.run_returncode,
            "source_reads": self.source_reads,
            "target_reads": self.target_reads,
            "invalid_reads": self.invalid_reads,
            "final_generation": self.final_generation,
            "compile_stdout": self.compile_stdout,
            "compile_stderr": self.compile_stderr,
            "run_stdout": self.run_stdout,
            "run_stderr": self.run_stderr,
            "truth_boundary": (
                "Success proves that two provenance-bound generated configurations compiled and completed the declared "
                "same-process logical-state migration, shadow-validation, atomic publication, concurrent immutable-reader, "
                "health-gate and rollback harness on one recorded local toolchain. It does not prove concurrent-writer "
                "migration, cross-process/distributed hot replacement, production availability, or performance superiority."
            ),
        }


def _base_result(bundle: GeneratedMigrationBundle) -> dict[str, Any]:
    return {
        "source_candidate_id": bundle.source_candidate_id,
        "target_candidate_id": bundle.target_candidate_id,
        "source_manifest_sha256": artifact_manifest_hash(bundle.source_manifest),
        "target_manifest_sha256": artifact_manifest_hash(bundle.target_manifest),
        "harness_sha256": bundle.harness_sha256,
    }


def _bounded_output(value: str | None, limit: int = 16_000) -> str:
    if not value:
        return ""
    return value[-limit:]


def _parse_counters(stdout: str) -> dict[str, int] | None:
    marker_line = next((line for line in stdout.splitlines() if _SUCCESS_MARKER in line), None)
    if marker_line is None:
        return None
    counters = {name: int(value) for name, value in _COUNTER_PATTERN.findall(marker_line)}
    required = {"source_reads", "target_reads", "invalid_reads", "final_generation"}
    if set(counters) != required:
        return None
    if counters["source_reads"] <= 0 or counters["target_reads"] <= 0:
        return None
    if counters["invalid_reads"] != 0 or counters["final_generation"] < 1:
        return None
    return counters


def verify_generated_migration_bundle(
    bundle: GeneratedMigrationBundle,
    *,
    compile_timeout_seconds: int = 120,
    run_timeout_seconds: int = 60,
) -> GeneratedMigrationVerificationResult:
    """Compile and execute one deterministic generated migration harness locally.

    Source bytes are produced by MORPHEUS, not accepted as arbitrary caller C++.
    The verifier uses one discovered compiler, a private temporary workspace,
    bounded subprocess timeouts and ``shell=False``. This is still host-process
    execution rather than a hardened container/VM/seccomp sandbox.
    """

    if compile_timeout_seconds < 1 or compile_timeout_seconds > 600:
        raise ValueError("compile_timeout_seconds must be in [1, 600]")
    if run_timeout_seconds < 1 or run_timeout_seconds > 600:
        raise ValueError("run_timeout_seconds must be in [1, 600]")

    base = _base_result(bundle)
    toolchain = discover_toolchain()
    if toolchain is None:
        return GeneratedMigrationVerificationResult(
            success=False,
            evidence_state="COMPILER_UNAVAILABLE",
            compiler=None,
            compiler_kind=None,
            compiler_version=None,
            compile_returncode=None,
            run_returncode=None,
            **base,
        )

    with tempfile.TemporaryDirectory(prefix="morpheus-generated-migration-") as temporary:
        directory = Path(temporary).resolve()
        source_header = directory / bundle.source_artifact.header_name
        target_header = directory / bundle.target_artifact.header_name
        source_path = directory / "generated_migration_harness.cpp"
        binary_path = directory / (
            "generated_migration_harness.exe" if toolchain.kind == "msvc" else "generated_migration_harness"
        )
        source_header.write_text(bundle.source_artifact.header_source, encoding="utf-8")
        target_header.write_text(bundle.target_artifact.header_source, encoding="utf-8")
        source_path.write_text(bundle.harness_source, encoding="utf-8")

        command = compile_command(
            toolchain,
            source=source_path,
            output=binary_path,
            include_dirs=[CORE_INCLUDE, directory],
            optimize=True,
        )
        if toolchain.kind != "msvc":
            command.append("-pthread")
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
        except subprocess.TimeoutExpired as exc:
            return GeneratedMigrationVerificationResult(
                success=False,
                evidence_state="GENERATED_MIGRATION_COMPILE_TIMED_OUT",
                compiler=toolchain.executable,
                compiler_kind=toolchain.kind,
                compiler_version=toolchain.version,
                compile_returncode=None,
                run_returncode=None,
                compile_stdout=_bounded_output(exc.stdout if isinstance(exc.stdout, str) else None),
                compile_stderr=_bounded_output(exc.stderr if isinstance(exc.stderr, str) else None),
                **base,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return GeneratedMigrationVerificationResult(
                success=False,
                evidence_state="GENERATED_MIGRATION_COMPILE_EXECUTION_ERROR",
                compiler=toolchain.executable,
                compiler_kind=toolchain.kind,
                compiler_version=toolchain.version,
                compile_returncode=None,
                run_returncode=None,
                compile_stderr=str(exc),
                **base,
            )

        compile_stdout = _bounded_output(compiled.stdout)
        compile_stderr = _bounded_output(compiled.stderr)
        if compiled.returncode != 0 or not binary_path.exists():
            return GeneratedMigrationVerificationResult(
                success=False,
                evidence_state="GENERATED_MIGRATION_COMPILE_FAILED",
                compiler=toolchain.executable,
                compiler_kind=toolchain.kind,
                compiler_version=toolchain.version,
                compile_returncode=compiled.returncode,
                run_returncode=None,
                compile_stdout=compile_stdout,
                compile_stderr=compile_stderr,
                **base,
            )

        try:
            executed = subprocess.run(
                [str(binary_path)],
                check=False,
                capture_output=True,
                text=True,
                timeout=run_timeout_seconds,
                env=environment,
                cwd=directory,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            return GeneratedMigrationVerificationResult(
                success=False,
                evidence_state="GENERATED_MIGRATION_RUN_TIMED_OUT",
                compiler=toolchain.executable,
                compiler_kind=toolchain.kind,
                compiler_version=toolchain.version,
                compile_returncode=compiled.returncode,
                run_returncode=None,
                compile_stdout=compile_stdout,
                compile_stderr=compile_stderr,
                run_stdout=_bounded_output(exc.stdout if isinstance(exc.stdout, str) else None),
                run_stderr=_bounded_output(exc.stderr if isinstance(exc.stderr, str) else None),
                **base,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return GeneratedMigrationVerificationResult(
                success=False,
                evidence_state="GENERATED_MIGRATION_RUN_EXECUTION_ERROR",
                compiler=toolchain.executable,
                compiler_kind=toolchain.kind,
                compiler_version=toolchain.version,
                compile_returncode=compiled.returncode,
                run_returncode=None,
                compile_stdout=compile_stdout,
                compile_stderr=compile_stderr,
                run_stderr=str(exc),
                **base,
            )

        run_stdout = _bounded_output(executed.stdout)
        run_stderr = _bounded_output(executed.stderr)
        if executed.returncode != 0:
            return GeneratedMigrationVerificationResult(
                success=False,
                evidence_state="GENERATED_MIGRATION_RUN_FAILED",
                compiler=toolchain.executable,
                compiler_kind=toolchain.kind,
                compiler_version=toolchain.version,
                compile_returncode=compiled.returncode,
                run_returncode=executed.returncode,
                compile_stdout=compile_stdout,
                compile_stderr=compile_stderr,
                run_stdout=run_stdout,
                run_stderr=run_stderr,
                **base,
            )

        counters = _parse_counters(executed.stdout)
        if counters is None:
            return GeneratedMigrationVerificationResult(
                success=False,
                evidence_state="GENERATED_MIGRATION_OUTPUT_PROVENANCE_FAILED",
                compiler=toolchain.executable,
                compiler_kind=toolchain.kind,
                compiler_version=toolchain.version,
                compile_returncode=compiled.returncode,
                run_returncode=executed.returncode,
                compile_stdout=compile_stdout,
                compile_stderr=compile_stderr,
                run_stdout=run_stdout,
                run_stderr=run_stderr,
                **base,
            )

        return GeneratedMigrationVerificationResult(
            success=True,
            evidence_state="COMPILE_AND_EXECUTION_VERIFIED_LOCAL_GENERATED_MIGRATION",
            compiler=toolchain.executable,
            compiler_kind=toolchain.kind,
            compiler_version=toolchain.version,
            compile_returncode=compiled.returncode,
            run_returncode=executed.returncode,
            source_reads=counters["source_reads"],
            target_reads=counters["target_reads"],
            invalid_reads=counters["invalid_reads"],
            final_generation=counters["final_generation"],
            compile_stdout=compile_stdout,
            compile_stderr=compile_stderr,
            run_stdout=run_stdout,
            run_stderr=run_stderr,
            **base,
        )
