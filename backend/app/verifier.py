from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .artifact_codegen import GeneratedArtifact
from .toolchain import base_environment, compile_command, discover_toolchain


@dataclass(frozen=True)
class CompileVerification:
    success: bool
    evidence_state: str
    compiler: str | None
    compiler_kind: str | None
    compiler_version: str | None
    source_sha256: str
    returncode: int | None
    stdout: str
    stderr: str
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
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "command_policy": self.command_policy,
            "limitations": self.limitations,
        }


def verify_generated_header_compile(
    artifact: GeneratedArtifact,
    *,
    timeout_seconds: int = 30,
) -> CompileVerification:
    """Compile an internally generated header using a fixed, non-shell command.

    Supports GCC, Clang, clang-cl and MSVC when available on PATH. This is a
    meaningful syntax/toolchain gate, but it is not a production sandbox and it
    is not the behavioral differential-correctness gate.
    """

    source_sha = hashlib.sha256(artifact.header_source.encode("utf-8")).hexdigest()
    toolchain = discover_toolchain()
    limitations = [
        "Compile success proves C++20 toolchain acceptance only; it does not prove logical correctness or performance.",
        "This verifier uses a local process with fixed arguments, not a hardened container/VM sandbox.",
    ]
    if toolchain is None:
        return CompileVerification(
            success=False,
            evidence_state="COMPILER_UNAVAILABLE",
            compiler=None,
            compiler_kind=None,
            compiler_version=None,
            source_sha256=source_sha,
            returncode=None,
            stdout="",
            stderr="No supported C++20 compiler (g++, clang++, clang-cl or cl) was found on PATH.",
            command_policy="FIXED_ARGUMENT_VECTOR_NO_SHELL",
            limitations=limitations,
        )

    repo_root = Path(__file__).resolve().parents[2]
    core_include = (repo_root / "core" / "include").resolve()
    if not (core_include / "morpheus" / "structures.hpp").is_file():
        return CompileVerification(
            success=False,
            evidence_state="CORE_INCLUDE_UNAVAILABLE",
            compiler=toolchain.executable,
            compiler_kind=toolchain.kind,
            compiler_version=toolchain.version,
            source_sha256=source_sha,
            returncode=None,
            stdout="",
            stderr="MORPHEUS primitive header is unavailable at the expected repository path.",
            command_policy="FIXED_ARGUMENT_VECTOR_NO_SHELL",
            limitations=limitations,
        )

    with tempfile.TemporaryDirectory(prefix="morpheus-verify-") as raw_directory:
        directory = Path(raw_directory)
        header_path = directory / artifact.header_name
        driver_path = directory / "compile_gate.cpp"
        binary_path = directory / ("compile_gate.exe" if os.name == "nt" or toolchain.kind == "msvc" else "compile_gate")
        header_path.write_text(artifact.header_source, encoding="utf-8")
        driver_path.write_text(
            f'''#include "{artifact.header_name}"\n\nint main() {{\n    morpheus_generated::GeneratedIndex index;\n    return index.candidate_id()[0] == '\\0';\n}}\n''',
            encoding="utf-8",
        )

        command = compile_command(
            toolchain,
            source=driver_path,
            output=binary_path,
            include_dirs=[core_include, directory],
            optimize=True,
        )
        try:
            process = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                cwd=directory,
                env=base_environment(raw_directory),
            )
        except subprocess.TimeoutExpired as exc:
            return CompileVerification(
                success=False,
                evidence_state="COMPILE_TIMEOUT",
                compiler=toolchain.executable,
                compiler_kind=toolchain.kind,
                compiler_version=toolchain.version,
                source_sha256=source_sha,
                returncode=None,
                stdout=(exc.stdout or "")[:8000] if isinstance(exc.stdout, str) else "",
                stderr="Compilation exceeded the fixed timeout.",
                command_policy="FIXED_ARGUMENT_VECTOR_NO_SHELL",
                limitations=limitations,
            )
        except OSError as exc:
            return CompileVerification(
                success=False,
                evidence_state="COMPILE_EXECUTION_ERROR",
                compiler=toolchain.executable,
                compiler_kind=toolchain.kind,
                compiler_version=toolchain.version,
                source_sha256=source_sha,
                returncode=None,
                stdout="",
                stderr=str(exc)[:8000],
                command_policy="FIXED_ARGUMENT_VECTOR_NO_SHELL",
                limitations=limitations,
            )

        success = process.returncode == 0 and binary_path.is_file()
        return CompileVerification(
            success=success,
            evidence_state="COMPILED_LOCAL_TOOLCHAIN" if success else "COMPILE_FAILED",
            compiler=toolchain.executable,
            compiler_kind=toolchain.kind,
            compiler_version=toolchain.version,
            source_sha256=source_sha,
            returncode=process.returncode,
            stdout=process.stdout[:8000],
            stderr=process.stderr[:8000],
            command_policy="FIXED_ARGUMENT_VECTOR_NO_SHELL",
            limitations=limitations,
        )
