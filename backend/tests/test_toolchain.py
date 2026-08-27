from __future__ import annotations

from pathlib import Path

from app.toolchain import Toolchain, compile_command, system_diagnostics


def test_gnu_compile_command_is_fixed_argument_vector(tmp_path: Path) -> None:
    toolchain = Toolchain(kind="gnu", executable="g++", version="test")
    source = tmp_path / "driver.cpp"
    output = tmp_path / "driver"
    command = compile_command(
        toolchain,
        source=source,
        output=output,
        include_dirs=[tmp_path / "include"],
    )
    assert command[0] == "g++"
    assert "-std=c++20" in command
    assert "-I" in command
    assert str(source.resolve()) in command
    assert str(output.resolve()) in command


def test_msvc_compile_command_uses_native_flags(tmp_path: Path) -> None:
    toolchain = Toolchain(kind="msvc", executable="cl.exe", version="test")
    source = tmp_path / "driver.cpp"
    output = tmp_path / "driver.exe"
    command = compile_command(
        toolchain,
        source=source,
        output=output,
        include_dirs=[tmp_path / "include"],
    )
    assert command[0] == "cl.exe"
    assert "/std:c++20" in command
    assert "/EHsc" in command
    assert any(item.startswith("/I") for item in command)
    assert f"/Fe:{output.resolve()}" in command


def test_system_diagnostics_preserves_truth_boundary() -> None:
    diagnostics = system_diagnostics()
    assert diagnostics["python"]
    assert diagnostics["platform"]
    assert diagnostics["evidence_state"] == "LOCAL_ENVIRONMENT_DIAGNOSTIC"
    assert isinstance(diagnostics["executables"], dict)
