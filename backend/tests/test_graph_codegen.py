from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from app.artifact_codegen import generate_verified_header
from app.engine import synthesize
from app.parser import parse_workload_text


REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_INCLUDE = REPO_ROOT / "core" / "include"

GRAPH_WORKLOAD = """
version: mws-0.1
name: graph-codegen-test
record_count: 5
fields:
  - name: node_id
    type: uint32
    cardinality: 5
queries:
  - kind: graph_traversal
    weight: 1.0
constraints:
  update_rate: 0
"""


def test_generated_csr_graph_compiles_and_preserves_topology_across_record_rebuilds(tmp_path: Path) -> None:
    compiler = shutil.which("g++") or shutil.which("clang++")
    if compiler is None:
        pytest.skip("C++20 compiler is unavailable in this environment")

    spec = parse_workload_text(GRAPH_WORKLOAD)
    synthesis = synthesize(spec)
    assert synthesis.winner is not None
    assert synthesis.winner.unique_primitives == ["csr_graph"]

    artifact = generate_verified_header(spec, synthesis.winner)
    assert '#include "morpheus/csr_graph.hpp"' in artifact.header_source
    assert "morpheus::CSRGraphIndex<std::uint32_t>" in artifact.header_source
    assert "configure_graph_0" in artifact.header_source
    assert "rebuild_record_indices" in artifact.header_source

    header = tmp_path / artifact.header_name
    header.write_text(artifact.header_source, encoding="utf-8")

    test_source = tmp_path / "generated_graph_self_test.cpp"
    test_source.write_text(
        f'''#include "{artifact.header_name}"

#include <cassert>
#include <cstdint>
#include <utility>
#include <vector>

int main() {{
    using Index = morpheus_generated::GeneratedIndex;
    using Record = Index::Record;

    Index index;
    index.configure_graph_0(
        5,
        std::vector<std::pair<std::uint32_t, std::uint32_t>>{{
            {{0, 1}}, {{0, 3}}, {{1, 2}}, {{3, 4}}, {{0, 1}}
        }},
        true
    );

    const auto depth_one = index.query_0(0, 1);
    assert((depth_one == std::vector<std::uint32_t>{{0, 1, 3}}));

    const auto depth_two = index.query_0(0, 2);
    assert((depth_two == std::vector<std::uint32_t>{{0, 1, 3, 2, 4}}));

    // Ordinary record mutations must not silently clear separately configured graph topology.
    index.insert(Record{{42}});
    index.update_at(0, Record{{43}});
    assert((index.query_0(0, 2) == depth_two));
    index.erase_at(0);
    assert((index.query_0(0, 2) == depth_two));

    return 0;
}}
''',
        encoding="utf-8",
    )

    binary = tmp_path / "generated_graph_self_test"
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
            str(test_source),
            "-o",
            str(binary),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert compile_process.returncode == 0, compile_process.stderr

    run_process = subprocess.run(
        [str(binary)],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert run_process.returncode == 0, run_process.stderr
