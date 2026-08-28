from __future__ import annotations

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


def test_generated_header_compiles_and_matches_reference_behavior(tmp_path: Path) -> None:
    compiler = shutil.which("g++") or shutil.which("clang++")
    if compiler is None:
        pytest.skip("C++20 compiler is unavailable in this environment")

    spec = parse_workload_text(EXAMPLE.read_text(encoding="utf-8"))
    synthesis = synthesize(spec)
    assert synthesis.winner is not None

    artifact = generate_verified_header(spec, synthesis.winner)
    assert '#include "morpheus/bplus_tree.hpp"' in artifact.header_source
    assert "morpheus::BPlusTreeIndex" in artifact.header_source
    assert "morpheus::OrderedTreeIndex" not in artifact.header_source

    header = tmp_path / artifact.header_name
    header.write_text(artifact.header_source, encoding="utf-8")

    test_source = tmp_path / "generated_self_test.cpp"
    test_source.write_text(
        f'''#include "{artifact.header_name}"

#include <cassert>
#include <string>
#include <vector>

int main() {{
    using Index = morpheus_generated::GeneratedIndex;
    using Record = Index::Record;

    Index index;
    index.insert(Record{{1, 24, "Pune"}});
    index.insert(Record{{2, 29, "Pune"}});
    index.insert(Record{{3, 42, "Nashik"}});

    const auto id_match = index.query_0(2);
    assert(id_match.size() == 1);
    assert((id_match.front() == Record{{2, 29, "Pune"}}));

    const auto age_range = index.query_1(20, 30);
    assert(age_range.size() == 2);

    const auto pune = index.query_2(std::string("Pune"));
    assert(pune.size() == 2);

    index.update_at(1, Record{{2, 35, "Mumbai"}});
    assert(index.query_0(2).size() == 1);
    assert(index.query_1(20, 30).size() == 1);
    assert(index.query_2(std::string("Pune")).size() == 1);
    assert(index.query_2(std::string("Mumbai")).size() == 1);

    index.erase_at(0);
    assert(index.query_0(1).empty());
    assert(index.records().size() == 2);
    return 0;
}}
''',
        encoding="utf-8",
    )

    binary = tmp_path / "generated_self_test"
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
