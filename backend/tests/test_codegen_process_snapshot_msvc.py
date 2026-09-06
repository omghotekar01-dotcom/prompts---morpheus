from __future__ import annotations

import os
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


def test_generated_index_process_snapshot_executes_under_msvc(tmp_path: Path) -> None:
    if os.name != "nt":
        pytest.skip("MSVC process-recovery proof is Windows-only")
    compiler = shutil.which("cl") or shutil.which("cl.exe")
    assert compiler is not None, "Windows native-recovery CI requires cl.exe in PATH"

    spec = parse_workload_text(EXAMPLE.read_text(encoding="utf-8"))
    synthesis = synthesize(spec)
    assert synthesis.winner is not None
    artifact = generate_verified_header(spec, synthesis.winner)
    (tmp_path / artifact.header_name).write_text(artifact.header_source, encoding="utf-8")

    source = tmp_path / "snapshot_msvc.cpp"
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

using Index = morpheus_generated::GeneratedIndex;
using Record = Index::Record;

std::string encode_record(const Record& record) {{
    std::ostringstream out;
    out << record.id << '\\n' << record.age << '\\n' << std::quoted(record.city);
    if (!out) throw std::runtime_error("encode failed");
    return out.str();
}}

Record decode_record(std::string_view payload) {{
    std::istringstream in{{std::string(payload)}};
    Record record{{}};
    if (!(in >> record.id >> record.age >> std::quoted(record.city))) throw std::runtime_error("decode failed");
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
        morpheus::write_portable_index_snapshot(out, index, encode_record);
        out.close();
        return out ? 0 : 4;
    }}
    if (mode == "read") {{
        std::ifstream in(path, std::ios::binary);
        if (!in) return 5;
        const auto restored = morpheus::read_portable_index_snapshot<Index>(in, decode_record);
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

    binary = tmp_path / "snapshot_msvc.exe"
    compiled = subprocess.run(
        [
            compiler,
            "/nologo",
            "/std:c++20",
            "/EHsc",
            "/W4",
            f"/I{CORE_INCLUDE}",
            f"/I{tmp_path}",
            str(source),
            f"/Fe:{binary}",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=90,
    )
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr

    snapshot = tmp_path / "msvc-logical.snapshot"
    writer = subprocess.run(
        [str(binary), "write", str(snapshot)],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert writer.returncode == 0, writer.stdout + writer.stderr

    reader = subprocess.run(
        [str(binary), "read", str(snapshot)],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert reader.returncode == 0, reader.stdout + reader.stderr
