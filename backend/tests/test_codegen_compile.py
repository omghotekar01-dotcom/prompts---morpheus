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
    assert '#include "morpheus/mutable_indices.hpp"' in artifact.header_source
    assert "morpheus::BPlusTreeIndex" in artifact.header_source
    assert "morpheus::MutableBitmapFilterIndex" in artifact.header_source
    assert "morpheus::OrderedTreeIndex" not in artifact.header_source
    assert "std::vector<std::optional<Record>> slots_" in artifact.header_source
    assert "std::vector<std::size_t> live_order_" in artifact.header_source
    assert "rebuild_record_indices" not in artifact.header_source

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
    assert(index.size() == 3);
    assert(index.records().size() == 3);

    // Preserve the historical generated-index rule: for unique-key primitives,
    // the last live record with a duplicate key wins.
    index.insert(Record{{2, 31, "Pune"}});
    const auto duplicate_winner = index.query_0(2);
    assert(duplicate_winner.size() == 1);
    assert((duplicate_winner.front() == Record{{2, 31, "Pune"}}));
    assert(index.query_2(std::string("Pune")).size() == 3);

    // Removing the duplicate must restore the previous live winner without a
    // full index rebuild and must remove only its bitmap posting.
    index.erase_at(3);
    const auto restored_winner = index.query_0(2);
    assert(restored_winner.size() == 1);
    assert((restored_winner.front() == Record{{2, 29, "Pune"}}));
    assert(index.query_2(std::string("Pune")).size() == 2);
    assert(index.size() == 3);

    index.update_at(1, Record{{2, 35, "Mumbai"}});
    assert(index.query_0(2).size() == 1);
    assert((index.query_0(2).front() == Record{{2, 35, "Mumbai"}}));
    assert(index.query_1(20, 30).size() == 1);
    assert(index.query_2(std::string("Pune")).size() == 1);
    assert(index.query_2(std::string("Mumbai")).size() == 1);

    // erase_at uses logical live-record position even though stable physical
    // slots retain tombstones from earlier deletions.
    index.erase_at(0);
    assert(index.query_0(1).empty());
    assert(index.records().size() == 2);
    assert(index.size() == 2);
    assert((index.records().front() == Record{{2, 35, "Mumbai"}}));

    // Cache must invalidate on later insertion while stable slot IDs remain valid.
    index.insert(Record{{4, 27, "Pune"}});
    assert(index.records().size() == 3);
    assert(index.query_0(4).size() == 1);
    assert(index.query_1(20, 30).size() == 1);
    assert(index.query_2(std::string("Pune")).size() == 1);

    // Shadow reconstruction checkpoint: a fresh generated object can ingest the
    // logical snapshot exported by records() and reconstruct equivalent physical
    // indexes without mutating the active object. This is the state-copy kernel
    // needed by a future cross-configuration VersionedSlot migration worker.
    const std::vector<Record> snapshot(index.records().begin(), index.records().end());
    Index shadow;
    for (const auto& record : snapshot) shadow.insert(record);
    assert(shadow.records() == snapshot);
    assert(shadow.records() == index.records());
    assert(shadow.query_0(2) == index.query_0(2));
    assert(shadow.query_0(4) == index.query_0(4));
    assert(shadow.query_1(20, 40) == index.query_1(20, 40));
    assert(shadow.query_2(std::string("Pune")) == index.query_2(std::string("Pune")));
    assert(shadow.query_2(std::string("Mumbai")) == index.query_2(std::string("Mumbai")));

    // Mutating the shadow proves it owns independent physical state; the active
    // object remains unchanged until an explicit version publication occurs.
    shadow.insert(Record{{5, 50, "Nashik"}});
    assert(shadow.size() == index.size() + 1);
    assert(index.query_0(5).empty());
    assert(shadow.query_0(5).size() == 1);
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
