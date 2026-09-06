from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest

from app.artifact_codegen import generate_verified_header
from app.engine import synthesize
from app.parser import parse_workload_text


REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = REPO_ROOT / "examples" / "users-demo.yaml"
CORE_INCLUDE = REPO_ROOT / "core" / "include"


def _compiler() -> str | None:
    return shutil.which("g++") or shutil.which("clang++")


def test_generated_index_logical_state_restores_in_fresh_process(tmp_path: Path) -> None:
    compiler = _compiler()
    if compiler is None:
        pytest.skip("C++20 compiler is unavailable in this environment")

    spec = parse_workload_text(EXAMPLE.read_text(encoding="utf-8"))
    synthesis = synthesize(spec)
    assert synthesis.winner is not None
    artifact = generate_verified_header(spec, synthesis.winner)

    header = tmp_path / artifact.header_name
    header.write_text(artifact.header_source, encoding="utf-8")
    source = tmp_path / "process_snapshot.cpp"
    source.write_text(
        f'''#include "{artifact.header_name}"
#include "morpheus/migration.hpp"

#include <cassert>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

using Index = morpheus_generated::GeneratedIndex;
using Record = Index::Record;

std::string encode_record(const Record& record) {{
    std::ostringstream out;
    out << record.id << '\\n' << record.age << '\\n' << std::quoted(record.city);
    if (!out) throw std::runtime_error("record encode failed");
    return out.str();
}}

Record decode_record(std::string_view payload) {{
    std::istringstream in{{std::string(payload)}};
    Record record{{}};
    if (!(in >> record.id >> record.age >> std::quoted(record.city))) {{
        throw std::runtime_error("record decode failed");
    }}
    in >> std::ws;
    if (!in.eof()) throw std::runtime_error("record payload has trailing data");
    return record;
}}

int main(int argc, char** argv) {{
    if (argc != 3) return 2;
    const std::string mode = argv[1];
    const std::string path = argv[2];

    if (mode == "write") {{
        Index index;
        index.insert(Record{{1, 24, "Pune"}});
        index.insert(Record{{2, 29, "Pune"}});
        index.insert(Record{{3, 42, "Nashik"}});
        index.update_at(1, Record{{2, 35, "Mumbai"}});
        index.erase_at(0);
        index.insert(Record{{4, 27, "Pune\\nWest \\\"A\\\""}});

        std::ofstream out(path, std::ios::binary | std::ios::trunc);
        if (!out) return 3;
        morpheus::write_portable_index_snapshot(out, index, encode_record);
        out.close();
        return out ? 0 : 4;
    }}

    if (mode == "read") {{
        std::ifstream in(path, std::ios::binary);
        if (!in) return 5;
        const auto restored = morpheus::read_portable_index_snapshot<Index>(in, decode_record);
        const std::vector<Record> expected{{
            Record{{2, 35, "Mumbai"}},
            Record{{3, 42, "Nashik"}},
            Record{{4, 27, "Pune\\nWest \\\"A\\\""}},
        }};
        assert(restored->records() == expected);
        assert(restored->size() == 3);
        assert(restored->query_0(2).size() == 1);
        assert(restored->query_0(4).size() == 1);
        assert(restored->query_1(20, 40).size() == 2);
        assert(restored->query_2(std::string("Mumbai")).size() == 1);
        assert(restored->query_2(std::string("Pune\\nWest \\\"A\\\"")).size() == 1);
        return 0;
    }}
    return 6;
}}
''',
        encoding="utf-8",
    )

    binary = tmp_path / "process_snapshot"
    compile_process = subprocess.run(
        [
            compiler,
            "-std=c++20",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
            "-I",
            str(CORE_INCLUDE),
            "-I",
            str(tmp_path),
            str(source),
            "-o",
            str(binary),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert compile_process.returncode == 0, compile_process.stderr

    snapshot = tmp_path / "logical.snapshot"
    write_process = subprocess.run(
        [str(binary), "write", str(snapshot)],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert write_process.returncode == 0, write_process.stderr
    original = snapshot.read_bytes()
    original_sha256 = hashlib.sha256(original).hexdigest()
    assert original.startswith(b"MORPHEUS_LOGICAL_INDEX_SNAPSHOT_V1\n3\n")

    read_process = subprocess.run(
        [str(binary), "read", str(snapshot)],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert read_process.returncode == 0, read_process.stderr
    assert snapshot.read_bytes() == original
    assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == original_sha256

    tampered = tmp_path / "tampered.snapshot"
    tampered.write_bytes(b"X" + original[1:])
    rejected = subprocess.run(
        [str(binary), "read", str(tampered)],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert rejected.returncode != 0

    oversized = tmp_path / "oversized.snapshot"
    oversized.write_bytes(b"MORPHEUS_LOGICAL_INDEX_SNAPSHOT_V1\n1000001\n")
    limited = subprocess.run(
        [str(binary), "read", str(oversized)],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert limited.returncode != 0
