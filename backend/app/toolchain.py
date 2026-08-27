from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Toolchain:
    kind: str
    executable: str
    version: str

    def as_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "executable": self.executable, "version": self.version}


def _run_version(executable: str, kind: str) -> str:
    args = [executable, "/Bv"] if kind == "msvc" else [executable, "--version"]
    try:
        process = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
            env=base_environment(),
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    text = (process.stdout or "") + "\n" + (process.stderr or "")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        lowered = line.lower()
        if kind == "msvc" and ("compiler version" in lowered or "microsoft" in lowered):
            return line[:400]
        if kind != "msvc":
            return line[:400]
    return "unknown"


def discover_toolchain() -> Toolchain | None:
    """Discover a C++20 compiler using an explicit override before PATH lookup.

    `MORPHEUS_CXX` may point at g++, clang++, clang-cl or cl.exe. The function
    intentionally returns one deterministic choice so evidence manifests can
    record exactly which toolchain accepted an artifact.
    """

    override = os.environ.get("MORPHEUS_CXX", "").strip()
    candidates: list[tuple[str, str]] = []
    if override:
        name = Path(override).name.lower()
        kind = "msvc" if name in {"cl", "cl.exe", "clang-cl", "clang-cl.exe"} else "gnu"
        candidates.append((kind, override))
    candidates.extend(
        [
            ("gnu", "g++"),
            ("gnu", "clang++"),
            ("msvc", "clang-cl"),
            ("msvc", "cl"),
        ]
    )

    seen: set[str] = set()
    for kind, candidate in candidates:
        resolved = shutil.which(candidate) if not Path(candidate).is_absolute() else candidate
        if not resolved:
            continue
        normalized = str(Path(resolved).resolve()) if Path(resolved).exists() else str(resolved)
        if normalized.lower() in seen:
            continue
        seen.add(normalized.lower())
        return Toolchain(kind=kind, executable=normalized, version=_run_version(normalized, kind))
    return None


def base_environment(temp_directory: str | Path | None = None) -> dict[str, str]:
    environment = os.environ.copy()
    environment["LANG"] = "C"
    environment["LC_ALL"] = "C"
    if temp_directory is not None:
        temp = str(Path(temp_directory).resolve())
        # GCC/Clang/MSYS2 and Windows-native tools disagree about which temp
        # variable is authoritative. Pin all common variants to the verifier's
        # private directory so no compiler falls back to C:\\WINDOWS.
        environment["TMPDIR"] = temp
        environment["TMP"] = temp
        environment["TEMP"] = temp
    return environment


def compile_command(
    toolchain: Toolchain,
    *,
    source: Path,
    output: Path,
    include_dirs: Iterable[Path],
    optimize: bool = True,
    warnings_as_errors: bool = False,
) -> list[str]:
    includes = [Path(item).resolve() for item in include_dirs]
    if toolchain.kind == "msvc":
        command = [
            toolchain.executable,
            "/nologo",
            "/std:c++20",
            "/EHsc",
            "/W4",
            "/O2" if optimize else "/Od",
        ]
        if warnings_as_errors:
            command.append("/WX")
        command.extend(f"/I{item}" for item in includes)
        command.extend([str(source.resolve()), f"/Fe:{output.resolve()}"])
        return command

    command = [
        toolchain.executable,
        "-std=c++20",
        "-O2" if optimize else "-O0",
        "-Wall",
        "-Wextra",
        "-Wpedantic",
        "-Werror=return-type",
    ]
    if warnings_as_errors:
        command.append("-Werror")
    for item in includes:
        command.extend(["-I", str(item)])
    command.extend([str(source.resolve()), "-o", str(output.resolve())])
    return command


def system_diagnostics() -> dict[str, object]:
    toolchain = discover_toolchain()
    candidates = {}
    for name in ("g++", "clang++", "clang-cl", "cl", "cmake"):
        candidates[name] = shutil.which(name)
    return {
        "python": sys.version.split()[0],
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "system": platform.system(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "toolchain": toolchain.as_dict() if toolchain else None,
        "executables": candidates,
        "morpheus_cxx_override": os.environ.get("MORPHEUS_CXX"),
        "evidence_state": "LOCAL_ENVIRONMENT_DIAGNOSTIC",
    }
