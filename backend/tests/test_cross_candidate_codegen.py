from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from app.artifact_codegen import ArtifactCodegenError, generate_verified_header
from app.engine import synthesize
from app.parser import parse_workload_text


REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = REPO_ROOT / "examples" / "users-demo.yaml"
CORE_INCLUDE = REPO_ROOT / "core" / "include"


def test_generated_candidate_namespaces_can_coexist_and_cross_rebuild(tmp_path: Path) -> None:
    compiler = shutil.which("g++") or shutil.which("clang++")
    if compiler is None:
        pytest.skip("C++20 compiler is unavailable in this environment")

    spec = parse_workload_text(EXAMPLE.read_text(encoding="utf-8"))
    synthesis = synthesize(spec)
    assert synthesis.winner is not None

    artifact_a = generate_verified_header(spec, synthesis.winner, namespace_name="morpheus_candidate_a")
    artifact_b = generate_verified_header(spec, synthesis.winner, namespace_name="morpheus_candidate_b")
    assert artifact_a.namespace_name == "morpheus_candidate_a"
    assert artifact_b.namespace_name == "morpheus_candidate_b"

    header_a = tmp_path / "candidate_a.hpp"
    header_b = tmp_path / "candidate_b.hpp"
    header_a.write_text(artifact_a.header_source, encoding="utf-8")
    header_b.write_text(artifact_b.header_source, encoding="utf-8")

    source = tmp_path / "cross_candidate.cpp"
    source.write_text(
        '''#include "candidate_a.hpp"
#include "candidate_b.hpp"
#include "morpheus/migration.hpp"

#include <cassert>
#include <string>

int main() {
    using Source = morpheus_candidate_a::GeneratedIndex;
    using Target = morpheus_candidate_b::GeneratedIndex;
    static_assert(morpheus::SnapshotMigratableIndex<Source>);
    static_assert(morpheus::SnapshotMigratableIndex<Target>);

    Source active;
    active.insert(Source::Record{1, 24, "Pune"});
    active.insert(Source::Record{2, 29, "Pune"});
    active.insert(Source::Record{3, 42, "Nashik"});

    const auto snapshot = morpheus::capture_index_snapshot(active);
    auto shadow = morpheus::rebuild_and_validate_foreign_index<Target>(
        snapshot,
        [](const Source::Record& record) {
            return Target::Record{record.id, record.age, record.city};
        },
        [&](const Target& candidate) {
            const auto by_id = candidate.query_0(2);
            const auto by_range = candidate.query_1(20, 30);
            const auto by_city = candidate.query_2(std::string("Pune"));
            return by_id.size() == 1 && by_range.size() == 2 && by_city.size() == 2;
        }
    );

    assert(shadow->size() == active.size());
    assert(shadow->query_0(2).size() == active.query_0(2).size());
    assert(shadow->query_1(20, 30).size() == active.query_1(20, 30).size());
    assert(shadow->query_2(std::string("Pune")).size() == active.query_2(std::string("Pune")).size());
    return 0;
}
''',
        encoding="utf-8",
    )

    binary = tmp_path / "cross_candidate"
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
    executed = subprocess.run([str(binary)], capture_output=True, text=True, check=False, timeout=30)
    assert executed.returncode == 0, executed.stderr


def test_generated_namespace_rejects_cpp_injection() -> None:
    spec = parse_workload_text(EXAMPLE.read_text(encoding="utf-8"))
    synthesis = synthesize(spec)
    assert synthesis.winner is not None
    with pytest.raises(ArtifactCodegenError):
        generate_verified_header(spec, synthesis.winner, namespace_name="bad; namespace injected")
