from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from app.artifact_codegen import generate_verified_header
from app.engine import synthesize
from app.parser import parse_workload_text
from app.toolchain import base_environment, compile_command, discover_toolchain


REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = REPO_ROOT / "examples" / "users-demo.yaml"
CORE_INCLUDE = REPO_ROOT / "core" / "include"


def test_generated_unique_routes_use_per_key_postings_without_full_record_scan(tmp_path: Path) -> None:
    toolchain = discover_toolchain()
    if toolchain is None:
        pytest.skip("C++20 compiler is unavailable in this environment")

    spec = parse_workload_text(EXAMPLE.read_text(encoding="utf-8"))
    synthesis = synthesize(spec)
    assert synthesis.winner is not None
    artifact = generate_verified_header(spec, synthesis.winner)

    # The old update/delete path reverse-scanned every live record to restore a
    # duplicate-key winner. Generated code now keeps a sorted live-slot posting
    # per unique physical key, so mutation work is bounded by that key's
    # duplicate set rather than total record count.
    assert "winner_slots_" in artifact.header_source
    assert "live_order_.rbegin()" not in artifact.header_source
    assert "MORPHEUS winner-slot invariant" in artifact.header_source

    header = tmp_path / artifact.header_name
    header.write_text(artifact.header_source, encoding="utf-8")
    driver = tmp_path / "mutation_postings.cpp"
    driver.write_text(
        f'''#include "{artifact.header_name}"

#include <cassert>
#include <string>

int main() {{
    using Index = morpheus_generated::GeneratedIndex;
    using Record = Index::Record;

    Index index;
    index.insert(Record{{7, 10, "A"}}); // stable slot 0
    index.insert(Record{{7, 20, "B"}}); // stable slot 1, current id=7 winner
    assert(index.query_0(7).size() == 1);
    assert(index.query_0(7).front().age == 20);

    // Updating the older duplicate without changing its key must not make it
    // the winner: winner order is stable logical insertion order, not mutation time.
    index.update_at(0, Record{{7, 30, "C"}});
    assert(index.query_0(7).size() == 1);
    assert(index.query_0(7).front().age == 20);

    // Moving the older slot to another key and back also preserves sorted slot
    // ordering in the per-key posting list.
    index.update_at(0, Record{{8, 31, "C"}});
    assert(index.query_0(7).front().age == 20);
    assert(index.query_0(8).front().age == 31);
    index.update_at(0, Record{{7, 32, "C"}});
    assert(index.query_0(7).front().age == 20);

    // Removing the later duplicate restores the older live slot immediately,
    // without scanning unrelated records.
    index.erase_at(1);
    assert(index.query_0(7).size() == 1);
    assert(index.query_0(7).front().age == 32);
    assert(index.size() == 1);
    return 0;
}}
''',
        encoding="utf-8",
    )

    binary = tmp_path / ("mutation_postings.exe" if os.name == "nt" or toolchain.kind == "msvc" else "mutation_postings")
    compiled = subprocess.run(
        compile_command(
            toolchain,
            source=driver,
            output=binary,
            include_dirs=[CORE_INCLUDE, tmp_path],
            optimize=False,
        ),
        capture_output=True,
        text=True,
        check=False,
        timeout=90,
        cwd=tmp_path,
        env=base_environment(tmp_path),
    )
    assert compiled.returncode == 0, compiled.stderr

    executed = subprocess.run(
        [str(binary)],
        capture_output=True,
        text=True,
        check=False,
        timeout=45,
        cwd=tmp_path,
        env=base_environment(tmp_path),
    )
    assert executed.returncode == 0, executed.stderr
