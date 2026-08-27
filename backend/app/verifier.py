from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .artifact_codegen import GeneratedArtifact


@dataclass(frozen=True)
class CompileVerification:
    success: bool
    evidence_state: str
    compiler: str | None
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
            "compiler_version": self.compiler_version,
            "source_sha256": self.source_sha256,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "command_policy": self.command_policy,
            "limitations": self.limitations,
        }


def _compiler() -> str | None:
    for candidate in ("g++", "clang++"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def _base_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["LANG"] = "C"
    environment["LC_ALL"] = "C"
    return environment


def _compiler_version(compiler: str) -> str:
    try:
        process = subprocess.run(
            [compiler, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
            env=_base_environment(),
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    line = (process.stdout or process.stderr).splitlines()
    return line[0][:300] if line else "unknown"


def verify_generated_header_compile(
    artifact: GeneratedArtifact,
    *,
    timeout_seconds: int = 30,
) -> CompileVerification:
    """Compile an internally generated header using a fixed, non-shell command.

    This is a meaningful syntax/toolchain gate, but it is not a production
    sandbox and it is not the differential correctness gate. The endpoint that
    uses this function must preserve that distinction.
    """

    source_sha = hashlib.sha256(artifact.header_source.encode("utf-8")).hexdigest()
    compiler = _compiler()
    limitations = [
        "Compile success proves C++20 toolchain acceptance only; it does not prove logical correctness or performance.",
        "This MVP verifier uses a local process with fixed arguments, not a hardened container/VM sandbox.",
    ]
    if compiler is None:
        return CompileVerification(
            success=False,
            evidence_state="COMPILER_UNAVAILABLE",
            compiler=None,
            compiler_version=None,
            source_sha256=source_sha,
            returncode=None,
            stdout="",
            stderr="No supported C++20 compiler (g++ or clang++) was found on PATH.",
            command_policy="FIXED_ARGUMENT_VECTOR_NO_SHELL",
            limitations=limitations,
        )

    repo_root = Path(__file__).resolve().parents[2]
    core_include = (repo_root / "core" / "include").resolve()
    if not (core_include / "morpheus" / "structures.hpp").is_file():
        return CompileVerification(
            success=False,
            evidence_state="CORE_INCLUDE_UNAVAILABLE",
            compiler=compiler,
            compiler_version=_compiler_version(compiler),
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
        binary_path = directory / ("compile_gate.exe" if os.name == "nt" else "compile_gate")
        header_path.write_text(artifact.header_source, encoding="utf-8")
        driver_path.write_text(
            f'''#include "{artifact.header_name}"\n\nint main() {{\n    morpheus_generated::GeneratedIndex index;\n    return index.candidate_id()[0] == '\\0';\n}}\n''',
            encoding="utf-8",
        )

        # GCC/Clang toolchains on Windows (especially MSYS2/MinGW) may consult
        # TEMP/TMP rather than TMPDIR. Point all common temp variables at the
        # verifier-owned directory so compilation never falls back to C:\\WINDOWS.
        environment = _base_environment()
        environment["TMPDIR"] = raw_directory
        environment["TMP"] = raw_directory
        environment["TEMP"] = raw_directory

        command = [
            compiler,
            "-std=c++20",
            "-O2",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
            "-Werror=return-type",
            "-I",
            str(core_include),
            "-I",
            str(directory),
            str(driver_path),
            "-o",
            str(binary_path),
        ]
        try:
            process = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                cwd=directory,
                env=environment,
            )
        except subprocess.TimeoutExpired as exc:
            return CompileVerification(
                success=False,
                evidence_state="COMPILE_TIMEOUT",
                compiler=compiler,
                compiler_version=_compiler_version(compiler),
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
                compiler=compiler,
                compiler_version=_compiler_version(compiler),
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
            compiler=compiler,
            compiler_version=_compiler_version(compiler),
            source_sha256=source_sha,
            returncode=process.returncode,
            stdout=process.stdout[:8000],
            stderr=process.stderr[:8000],
            command_policy="FIXED_ARGUMENT_VECTOR_NO_SHELL",
            limitations=limitations,
        )
