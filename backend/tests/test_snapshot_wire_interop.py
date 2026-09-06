from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from app.artifact_codegen import generate_verified_header
from app.engine import synthesize
from app.parser import parse_workload_text
from app.process_transfer import inspect_identified_snapshot
from app.schema_identity import generated_record_schema_identity


REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = REPO_ROOT / "examples" / "users-demo.yaml"
CORE_INCLUDE = REPO_ROOT / "core" / "include"
CODEC_IDENTITY = "morpheus-wire-interop-text-codec-v1"


def _compiler() -> tuple[str, str] | None:
    if os.name == "nt":
        compiler = shutil.which("cl") or shutil.which("cl.exe")
        return (compiler, "msvc") if compiler else None
    compiler = shutil.which("g++") or shutil.which("clang++")
    return (compiler, "gnu") if compiler else None


def _compile(
    compiler: str,
    family: str,
    source: Path,
    binary: Path,
    include_dir: Path,
) -> subprocess.CompletedProcess[str]:
    if family == "msvc":
        command = [
            compiler,
            "/nologo",
            "/std:c++20",
            "/EHsc",
            "/W4",
            f"/I{CORE_INCLUDE}",
            f"/I{include_dir}",
            str(source),
            f"/Fe:{binary}",
        ]
    else:
        command = [
            compiler,
            "-std=c++20",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
            "-I",
            str(CORE_INCLUDE),
            "-I",
            str(include_dir),
            str(source),
            "-o",
            str(binary),
        ]
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        timeout=90,
    )


def test_cpp_identified_snapshot_bytes_match_python_control_plane_parser(tmp_path: Path) -> None:
    selected = _compiler()
    if selected is None:
        if os.name == "nt":
            pytest.fail("Windows snapshot-wire interoperability requires cl.exe in PATH")
        pytest.skip("C++20 compiler is unavailable in this environment")
    compiler, family = selected

    spec = parse_workload_text(EXAMPLE.read_text(encoding="utf-8"))
    synthesis = synthesize(spec)
    assert synthesis.winner is not None
    artifact = generate_verified_header(spec, synthesis.winner)
    schema_identity = generated_record_schema_identity(spec)
    (tmp_path / artifact.header_name).write_text(artifact.header_source, encoding="utf-8")

    source = tmp_path / "wire_interop.cpp"
    source.write_text(
        f'''#include "{artifact.header_name}"
#include "morpheus/identified_migration.hpp"

#include <cassert>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>

using Index = morpheus_generated::GeneratedIndex;
using Record = Index::Record;
constexpr std::string_view kSchema = "{schema_identity}";
constexpr std::string_view kCodec = "{CODEC_IDENTITY}";

std::string encode_record(const Record& record) {{
    std::ostringstream out;
    out << record.id << '\\n' << record.age << '\\n' << std::quoted(record.city);
    if (!out) throw std::runtime_error("encode failed");
    return out.str();
}}

Record decode_record(std::string_view payload) {{
    std::istringstream in{{std::string(payload)}};
    Record record{{}};
    if (!(in >> record.id >> record.age >> std::quoted(record.city))) {{
        throw std::runtime_error("decode failed");
    }}
    in >> std::ws;
    if (!in.eof()) throw std::runtime_error("trailing record bytes");
    return record;
}}

int main(int argc, char** argv) {{
    if (argc != 3) return 2;
    const std::string mode = argv[1];
    const std::string path = argv[2];
    if (mode == "write") {{
        Index index;
        index.insert(Record{{1, 24, "Pune"}});
        index.insert(Record{{2, 35, "Mumbai"}});
        index.insert(Record{{3, 42, "Nashik"}});
        std::ofstream out(path, std::ios::binary | std::ios::trunc);
        if (!out) return 3;
        morpheus::write_identified_portable_index_snapshot(out, index, kSchema, kCodec, encode_record);
        out.close();
        return out ? 0 : 4;
    }}
    if (mode == "read") {{
        std::ifstream in(path, std::ios::binary);
        if (!in) return 5;
        const auto restored = morpheus::read_identified_portable_index_snapshot<Index>(
            in, kSchema, kCodec, decode_record
        );
        assert(restored->size() == 3);
        assert(restored->query_0(1).size() == 1);
        assert(restored->query_0(2).size() == 1);
        assert(restored->query_1(20, 40).size() == 2);
        assert(restored->query_2(std::string("Mumbai")).size() == 1);
        return 0;
    }}
    return 6;
}}
''',
        encoding="utf-8",
    )

    binary = tmp_path / ("wire_interop.exe" if family == "msvc" else "wire_interop")
    compiled = _compile(compiler, family, source, binary, tmp_path)
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr

    snapshot = tmp_path / "wire.snapshot"
    writer = subprocess.run(
        [str(binary), "write", str(snapshot)],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert writer.returncode == 0, writer.stdout + writer.stderr

    emitted = snapshot.read_bytes()
    inspection = inspect_identified_snapshot(
        emitted,
        expected_schema_identity=schema_identity,
        expected_codec_identity=CODEC_IDENTITY,
    )
    assert inspection.record_count == 3
    assert inspection.total_record_bytes > 0
    assert inspection.snapshot_size_bytes == len(emitted)
    assert inspection.snapshot_sha256 == hashlib.sha256(emitted).hexdigest()

    with pytest.raises(ValueError, match="codec identity mismatch"):
        inspect_identified_snapshot(
            emitted,
            expected_schema_identity=schema_identity,
            expected_codec_identity="morpheus-wire-interop-wrong-codec-v1",
        )

    reader = subprocess.run(
        [str(binary), "read", str(snapshot)],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert reader.returncode == 0, reader.stdout + reader.stderr
    assert snapshot.read_bytes() == emitted
