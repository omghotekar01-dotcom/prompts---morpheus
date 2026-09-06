from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from app.artifact_codegen import generate_verified_header
from app.engine import synthesize
from app.parser import parse_workload_text
from app.schema_identity import GENERATED_RECORD_SCHEMA_PREFIX, generated_record_schema_identity


REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = REPO_ROOT / "examples" / "users-demo.yaml"
CORE_INCLUDE = REPO_ROOT / "core" / "include"
CODEC_IDENTITY = "morpheus-test-record-text-codec-v1"


def _compiler() -> str | None:
    return shutil.which("g++") or shutil.which("clang++")


def test_generated_record_schema_identity_tracks_logical_contract_only() -> None:
    source = EXAMPLE.read_text(encoding="utf-8")
    base = parse_workload_text(source)
    identity = generated_record_schema_identity(base)

    assert re.fullmatch(r"morpheus-record-schema-v1:[0-9a-f]{64}", identity)
    assert identity.startswith(GENERATED_RECORD_SCHEMA_PREFIX)

    renamed_workload = parse_workload_text(source.replace("name: users_demo", "name: users_demo_copy", 1))
    aliases = source.replace("type: uint64", "type: uint64_t", 1)
    aliases = aliases.replace("type: uint32", "type: uint32_t", 1)
    aliases = aliases.replace("type: string", "type: text", 1)
    alias_spec = parse_workload_text(aliases)

    assert generated_record_schema_identity(renamed_workload) == identity
    assert generated_record_schema_identity(alias_spec) == identity

    renamed_field = source.replace("name: city", "name: region", 1).replace("field: city", "field: region", 1)
    changed_type = source.replace("type: uint32", "type: uint64", 1)
    reordered = source.replace(
        "  - name: id\n    type: uint64\n    cardinality: 100000\n"
        "  - name: age\n    type: uint32\n    cardinality: 90\n",
        "  - name: age\n    type: uint32\n    cardinality: 90\n"
        "  - name: id\n    type: uint64\n    cardinality: 100000\n",
        1,
    )

    assert generated_record_schema_identity(parse_workload_text(renamed_field)) != identity
    assert generated_record_schema_identity(parse_workload_text(changed_type)) != identity
    assert generated_record_schema_identity(parse_workload_text(reordered)) != identity


def test_identified_snapshot_uses_generated_schema_identity_before_decode(tmp_path: Path) -> None:
    compiler = _compiler()
    if compiler is None:
        pytest.skip("C++20 compiler is unavailable in this environment")

    spec = parse_workload_text(EXAMPLE.read_text(encoding="utf-8"))
    synthesis = synthesize(spec)
    assert synthesis.winner is not None
    artifact = generate_verified_header(spec, synthesis.winner)
    schema_identity = generated_record_schema_identity(spec)

    (tmp_path / artifact.header_name).write_text(artifact.header_source, encoding="utf-8")
    source = tmp_path / "schema_snapshot.cpp"
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

    if (mode == "wrong-schema") {{
        std::ifstream in(path, std::ios::binary);
        if (!in) return 5;
        try {{
            (void)morpheus::read_identified_portable_index_snapshot<Index>(
                in, "morpheus-record-schema-v1:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
                kCodec,
                [](std::string_view) -> Record {{ throw std::runtime_error("decoder must not run"); }}
            );
        }} catch (const std::runtime_error& error) {{
            return std::string_view(error.what()).find("schema identity mismatch") != std::string_view::npos ? 0 : 7;
        }}
        return 8;
    }}
    return 9;
}}
''',
        encoding="utf-8",
    )

    binary = tmp_path / "schema_snapshot"
    compiled = subprocess.run(
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
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert compiled.returncode == 0, compiled.stderr

    snapshot = tmp_path / "schema.snapshot"
    writer = subprocess.run([str(binary), "write", str(snapshot)], capture_output=True, text=True, check=False, timeout=30)
    assert writer.returncode == 0, writer.stderr
    assert snapshot.read_bytes().startswith(b"MORPHEUS_IDENTIFIED_LOGICAL_INDEX_SNAPSHOT_V1\n")

    reader = subprocess.run([str(binary), "read", str(snapshot)], capture_output=True, text=True, check=False, timeout=30)
    assert reader.returncode == 0, reader.stderr

    rejected = subprocess.run(
        [str(binary), "wrong-schema", str(snapshot)], capture_output=True, text=True, check=False, timeout=30
    )
    assert rejected.returncode == 0, rejected.stderr
