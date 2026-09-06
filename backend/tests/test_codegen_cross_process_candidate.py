from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest

from app.artifact_codegen import generate_verified_header
from app.engine import synthesize
from app.models import QueryKind
from app.parser import parse_workload_text


REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = REPO_ROOT / "examples" / "users-demo.yaml"
CORE_INCLUDE = REPO_ROOT / "core" / "include"


def _compiler() -> str | None:
    return shutil.which("g++") or shutil.which("clang++")


def test_logical_snapshot_crosses_process_and_physical_candidate_boundary(tmp_path: Path) -> None:
    compiler = _compiler()
    if compiler is None:
        pytest.skip("C++20 compiler is unavailable in this environment")

    spec = parse_workload_text(EXAMPLE.read_text(encoding="utf-8"))
    synthesis = synthesize(spec)
    assert synthesis.winner is not None
    source_candidate = synthesis.winner

    target_assignments = []
    for assignment in source_candidate.assignments:
        primitive = assignment.primitive
        if assignment.query_kind == QueryKind.POINT_LOOKUP:
            primitive = "ordered_tree" if primitive != "ordered_tree" else "robin_hood_hash"
        elif assignment.query_kind == QueryKind.RANGE_SCAN:
            primitive = "sorted_array" if primitive != "sorted_array" else "ordered_tree"
        target_assignments.append(assignment.model_copy(update={"primitive": primitive}))

    assert [item.primitive for item in target_assignments] != [item.primitive for item in source_candidate.assignments]
    target_candidate = source_candidate.model_copy(
        update={
            "id": source_candidate.id + "-process-target",
            "assignments": target_assignments,
            "unique_primitives": sorted({item.primitive for item in target_assignments}),
        }
    )

    source_artifact = generate_verified_header(spec, source_candidate, namespace_name="morpheus_process_source")
    target_artifact = generate_verified_header(spec, target_candidate, namespace_name="morpheus_process_target")
    (tmp_path / "source.hpp").write_text(source_artifact.header_source, encoding="utf-8")
    (tmp_path / "target.hpp").write_text(target_artifact.header_source, encoding="utf-8")

    source = tmp_path / "cross_process_candidate.cpp"
    source.write_text(
        '''#include "source.hpp"
#include "target.hpp"
#include "morpheus/migration.hpp"

#include <cassert>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

using Source = morpheus_process_source::GeneratedIndex;
using Target = morpheus_process_target::GeneratedIndex;

std::string encode_record(const Source::Record& record) {
    std::ostringstream out;
    out << record.id << '\\n' << record.age << '\\n' << std::quoted(record.city);
    if (!out) throw std::runtime_error("record encode failed");
    return out.str();
}

Target::Record decode_record(std::string_view payload) {
    std::istringstream in{std::string(payload)};
    Target::Record record{};
    if (!(in >> record.id >> record.age >> std::quoted(record.city))) {
        throw std::runtime_error("record decode failed");
    }
    in >> std::ws;
    if (!in.eof()) throw std::runtime_error("record payload has trailing data");
    return record;
}

int main(int argc, char** argv) {
    if (argc != 3) return 2;
    const std::string mode = argv[1];
    const std::string path = argv[2];

    if (mode == "write") {
        Source source;
        source.insert(Source::Record{1, 24, "Pune"});
        source.insert(Source::Record{2, 29, "Pune"});
        source.insert(Source::Record{3, 42, "Nashik"});
        source.update_at(1, Source::Record{2, 35, "Mumbai"});
        source.erase_at(0);
        source.insert(Source::Record{4, 27, "Pune"});

        std::ofstream out(path, std::ios::binary | std::ios::trunc);
        if (!out) return 3;
        morpheus::write_portable_index_snapshot(out, source, encode_record);
        out.close();
        return out ? 0 : 4;
    }

    if (mode == "read") {
        std::ifstream in(path, std::ios::binary);
        if (!in) return 5;
        const auto target = morpheus::read_portable_index_snapshot<Target>(in, decode_record);
        const std::vector<Target::Record> expected{
            Target::Record{2, 35, "Mumbai"},
            Target::Record{3, 42, "Nashik"},
            Target::Record{4, 27, "Pune"},
        };
        assert(target->records() == expected);
        assert(target->size() == expected.size());
        assert(target->query_0(2).size() == 1);
        assert(target->query_0(4).size() == 1);
        assert(target->query_1(20, 40).size() == 2);
        assert(target->query_2(std::string("Mumbai")).size() == 1);
        assert(target->query_2(std::string("Pune")).size() == 1);
        return 0;
    }
    return 6;
}
''',
        encoding="utf-8",
    )

    binary = tmp_path / "cross_process_candidate"
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

    snapshot = tmp_path / "cross-candidate.snapshot"
    writer = subprocess.run(
        [str(binary), "write", str(snapshot)],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert writer.returncode == 0, writer.stderr
    payload = snapshot.read_bytes()
    payload_sha256 = hashlib.sha256(payload).hexdigest()

    reader = subprocess.run(
        [str(binary), "read", str(snapshot)],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert reader.returncode == 0, reader.stderr
    assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == payload_sha256
