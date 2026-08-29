from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .generated_migration_benchmark import (
    CORE_INCLUDE,
    GeneratedMigrationBenchmarkReport,
    MigrationBenchmarkConfig,
    _bounded,
    _parse_rows,
    _report_base,
    build_generated_migration_benchmark_source,
)
from .generated_migration_bundle import GeneratedMigrationBundle
from .toolchain import base_environment, compile_command, discover_toolchain


class PreparedGeneratedMigrationBenchmark:
    """Compile one generated source/target benchmark binary and reuse it.

    RQ7 factor cells vary only runtime options (reader count, transitions,
    repetitions and record count). Recompiling identical generated C++ for every
    cell adds avoidable campaign time and creates more opportunities for
    environment drift. This session binds one source hash, one selected
    toolchain, one private workspace and one binary to all cells executed through
    it. It is a host-process measurement tool, not a sandbox.
    """

    def __init__(
        self,
        bundle: GeneratedMigrationBundle,
        spec: Any,
        *,
        compile_timeout_seconds: int = 120,
    ) -> None:
        if not 1 <= compile_timeout_seconds <= 600:
            raise ValueError("compile_timeout_seconds must be in [1, 600]")
        self.bundle = bundle
        self.spec = spec
        self.compile_timeout_seconds = compile_timeout_seconds
        self.benchmark_source = build_generated_migration_benchmark_source(bundle, spec)
        import hashlib

        self.source_sha = hashlib.sha256(self.benchmark_source.encode("utf-8")).hexdigest()
        self.base = _report_base(bundle, self.source_sha)
        self.toolchain = discover_toolchain()
        self._temporary: tempfile.TemporaryDirectory[str] | None = None
        self.directory: Path | None = None
        self.binary_path: Path | None = None
        self.environment: dict[str, str] | None = None
        self.compile_returncode: int | None = None
        self.compile_stdout = ""
        self.compile_stderr = ""
        self.setup_evidence_state: str | None = None
        self.compile_invocations = 0
        self.run_invocations = 0

    def __enter__(self) -> "PreparedGeneratedMigrationBenchmark":
        if self.toolchain is None:
            self.setup_evidence_state = "COMPILER_UNAVAILABLE"
            return self
        self._temporary = tempfile.TemporaryDirectory(prefix="morpheus-generated-migration-campaign-")
        self.directory = Path(self._temporary.name).resolve()
        (self.directory / self.bundle.source_artifact.header_name).write_text(
            self.bundle.source_artifact.header_source,
            encoding="utf-8",
        )
        (self.directory / self.bundle.target_artifact.header_name).write_text(
            self.bundle.target_artifact.header_source,
            encoding="utf-8",
        )
        source_path = self.directory / "generated_migration_benchmark.cpp"
        source_path.write_text(self.benchmark_source, encoding="utf-8")
        self.binary_path = self.directory / (
            "generated_migration_benchmark.exe" if self.toolchain.kind == "msvc" else "generated_migration_benchmark"
        )
        command = compile_command(
            self.toolchain,
            source=source_path,
            output=self.binary_path,
            include_dirs=[CORE_INCLUDE, self.directory],
            optimize=True,
        )
        if self.toolchain.kind != "msvc":
            command.append("-pthread")
        self.environment = base_environment(self.directory)
        self.compile_invocations += 1
        try:
            compiled = subprocess.run(
                command,
                cwd=self.directory,
                env=self.environment,
                shell=False,
                capture_output=True,
                text=True,
                timeout=self.compile_timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            self.setup_evidence_state = "GENERATED_MIGRATION_BENCHMARK_COMPILE_TIMED_OUT"
            return self
        self.compile_returncode = compiled.returncode
        self.compile_stdout = _bounded(compiled.stdout)
        self.compile_stderr = _bounded(compiled.stderr)
        if compiled.returncode != 0 or not self.binary_path.exists():
            self.setup_evidence_state = "GENERATED_MIGRATION_BENCHMARK_COMPILE_FAILED"
        return self

    def close(self) -> None:
        if self._temporary is not None:
            self._temporary.cleanup()
            self._temporary = None
        self.directory = None
        self.binary_path = None
        self.environment = None

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def _setup_failure(self, config: MigrationBenchmarkConfig) -> GeneratedMigrationBenchmarkReport:
        state = self.setup_evidence_state or "GENERATED_MIGRATION_BENCHMARK_NOT_PREPARED"
        return GeneratedMigrationBenchmarkReport(
            False,
            state,
            compiler=self.toolchain.executable if self.toolchain else None,
            compiler_kind=self.toolchain.kind if self.toolchain else None,
            compiler_version=self.toolchain.version if self.toolchain else None,
            config=config,
            rows=(),
            compile_returncode=self.compile_returncode,
            run_returncode=None,
            compile_stdout=self.compile_stdout,
            compile_stderr=self.compile_stderr,
            **self.base,
        )

    def run(
        self,
        config: MigrationBenchmarkConfig,
        *,
        run_timeout_seconds: int = 120,
    ) -> GeneratedMigrationBenchmarkReport:
        config.validate()
        if not 1 <= run_timeout_seconds <= 600:
            raise ValueError("run_timeout_seconds must be in [1, 600]")
        if self.setup_evidence_state is not None or self.toolchain is None:
            return self._setup_failure(config)
        if self.directory is None or self.binary_path is None or self.environment is None:
            raise RuntimeError("prepared generated migration benchmark must be entered before run()")
        if self.compile_returncode != 0 or not self.binary_path.exists():
            return self._setup_failure(config)

        run_command = [
            str(self.binary_path),
            "--readers",
            str(config.readers),
            "--transitions",
            str(config.transitions),
            "--repetitions",
            str(config.repetitions),
            "--record-count",
            str(config.record_count),
        ]
        self.run_invocations += 1
        try:
            executed = subprocess.run(
                run_command,
                cwd=self.directory,
                env=self.environment,
                shell=False,
                capture_output=True,
                text=True,
                timeout=run_timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return GeneratedMigrationBenchmarkReport(
                False,
                "GENERATED_MIGRATION_BENCHMARK_RUN_TIMED_OUT",
                compiler=self.toolchain.executable,
                compiler_kind=self.toolchain.kind,
                compiler_version=self.toolchain.version,
                config=config,
                rows=(),
                compile_returncode=self.compile_returncode,
                run_returncode=None,
                compile_stdout=self.compile_stdout,
                compile_stderr=self.compile_stderr,
                **self.base,
            )

        run_stdout = _bounded(executed.stdout)
        run_stderr = _bounded(executed.stderr)
        if executed.returncode != 0:
            return GeneratedMigrationBenchmarkReport(
                False,
                "GENERATED_MIGRATION_BENCHMARK_RUN_FAILED",
                compiler=self.toolchain.executable,
                compiler_kind=self.toolchain.kind,
                compiler_version=self.toolchain.version,
                config=config,
                rows=(),
                compile_returncode=self.compile_returncode,
                run_returncode=executed.returncode,
                compile_stdout=self.compile_stdout,
                compile_stderr=self.compile_stderr,
                run_stdout=run_stdout,
                run_stderr=run_stderr,
                **self.base,
            )
        try:
            rows = _parse_rows(executed.stdout, config)
        except (TypeError, ValueError) as exc:
            return GeneratedMigrationBenchmarkReport(
                False,
                "GENERATED_MIGRATION_BENCHMARK_OUTPUT_INVALID",
                compiler=self.toolchain.executable,
                compiler_kind=self.toolchain.kind,
                compiler_version=self.toolchain.version,
                config=config,
                rows=(),
                compile_returncode=self.compile_returncode,
                run_returncode=executed.returncode,
                compile_stdout=self.compile_stdout,
                compile_stderr=self.compile_stderr,
                run_stdout=run_stdout,
                run_stderr=str(exc),
                **self.base,
            )

        state = (
            "MEASURED_CI_SMOKE_GENERATED_MIGRATION_TRANSITION_COST"
            if os.environ.get("GITHUB_ACTIONS") == "true"
            else "MEASURED_LOCAL_PROCESS_GENERATED_MIGRATION_TRANSITION_COST"
        )
        return GeneratedMigrationBenchmarkReport(
            True,
            state,
            compiler=self.toolchain.executable,
            compiler_kind=self.toolchain.kind,
            compiler_version=self.toolchain.version,
            config=config,
            rows=rows,
            compile_returncode=self.compile_returncode,
            run_returncode=executed.returncode,
            compile_stdout=self.compile_stdout,
            compile_stderr=self.compile_stderr,
            run_stdout=run_stdout,
            run_stderr=run_stderr,
            **self.base,
        )


def prepare_generated_migration_benchmark(
    bundle: GeneratedMigrationBundle,
    spec: Any,
    *,
    compile_timeout_seconds: int = 120,
) -> PreparedGeneratedMigrationBenchmark:
    return PreparedGeneratedMigrationBenchmark(
        bundle,
        spec,
        compile_timeout_seconds=compile_timeout_seconds,
    )
