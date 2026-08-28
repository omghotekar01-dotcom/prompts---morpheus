from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from app.artifact_codegen import generate_verified_header
from app.models import (
    Assignment,
    CandidateResult,
    FieldSpec,
    QueryKind,
    QuerySpec,
    WorkloadSpec,
)
from app.toolchain import base_environment, compile_command, discover_toolchain


REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_INCLUDE = REPO_ROOT / "core" / "include"


def _spec() -> WorkloadSpec:
    return WorkloadSpec(
        name="duplicate_semantics",
        record_count=1000,
        fields=[
            FieldSpec(name="id", type="uint64", cardinality=1000),
            FieldSpec(name="age", type="uint32", cardinality=100),
            FieldSpec(name="name", type="string", cardinality=500),
        ],
        queries=[
            QuerySpec(kind=QueryKind.POINT_LOOKUP, field="id", weight=0.3),
            QuerySpec(kind=QueryKind.RANGE_SCAN, field="age", weight=0.35, selectivity=0.1),
            QuerySpec(kind=QueryKind.PREFIX_SEARCH, field="name", weight=0.35),
        ],
    )


def _candidate() -> CandidateResult:
    return CandidateResult(
        id="duplicate_semantics",
        assignments=[
            Assignment(query_index=0, query_kind=QueryKind.POINT_LOOKUP, field="id", primitive="robin_hood_hash"),
            Assignment(query_index=1, query_kind=QueryKind.RANGE_SCAN, field="age", primitive="ordered_tree"),
            Assignment(query_index=2, query_kind=QueryKind.PREFIX_SEARCH, field="name", primitive="radix_trie"),
        ],
        unique_primitives=["robin_hood_hash", "ordered_tree", "radix_trie"],
        predicted_latency_us=1.0,
        predicted_memory_mb=1.0,
        predicted_build_ms=1.0,
        predicted_update_us=1.0,
        score=1.0,
        feasible=True,
    )


def test_generated_range_and_prefix_routes_preserve_duplicate_records(tmp_path: Path) -> None:
    toolchain = discover_toolchain()
    if toolchain is None:
        pytest.skip("C++20 compiler is unavailable in this environment")

    artifact = generate_verified_header(_spec(), _candidate())
    assert "BPlusTreeIndex<std::pair<std::uint32_t, std::size_t>" in artifact.header_source
    assert "MutableMultiPrefixTrie<std::size_t>" in artifact.header_source
    assert "physical_low" in artifact.header_source
    assert "physical_high" in artifact.header_source

    header = tmp_path / artifact.header_name
    header.write_text(artifact.header_source, encoding="utf-8")
    driver = tmp_path / "duplicate_semantics.cpp"
    driver.write_text(
        f'''#include "{artifact.header_name}"

#include <algorithm>
#include <cassert>
#include <cstdint>
#include <string>
#include <vector>

int main() {{
    using Index = morpheus_generated::GeneratedIndex;
    using Record = Index::Record;

    Index index;
    index.insert(Record{{1, 30, "alpha"}});
    index.insert(Record{{2, 30, "alpha"}});
    index.insert(Record{{3, 30, "alpine"}});
    index.insert(Record{{4, 40, "beta"}});

    auto ids = [](const std::vector<Record>& rows) {{
        std::vector<std::uint64_t> out;
        for (const auto& row : rows) out.push_back(row.id);
        std::sort(out.begin(), out.end());
        return out;
    }};

    // Equal logical range keys must remain distinct physical entries.
    assert((ids(index.query_1(30, 30)) == std::vector<std::uint64_t>{{1, 2, 3}}));
    assert((ids(index.query_1(30, 40)) == std::vector<std::uint64_t>{{1, 2, 3, 4}}));

    // Equal exact strings and different strings sharing a prefix must all be
    // returned. A limit applies to logical records, not merely distinct keys.
    assert((ids(index.query_2(std::string("al"), 100)) == std::vector<std::uint64_t>{{1, 2, 3}}));
    assert(index.query_2(std::string("al"), 2).size() == 2);
    assert((ids(index.query_2(std::string("alpha"), 100)) == std::vector<std::uint64_t>{{1, 2}}));

    // Update one duplicate across both indexed fields. Stable slot identity is
    // retained while the old physical postings are removed and new ones added.
    index.update_at(1, Record{{2, 40, "beta"}});
    assert((ids(index.query_1(30, 30)) == std::vector<std::uint64_t>{{1, 3}}));
    assert((ids(index.query_1(40, 40)) == std::vector<std::uint64_t>{{2, 4}}));
    assert((ids(index.query_2(std::string("al"), 100)) == std::vector<std::uint64_t>{{1, 3}}));
    assert((ids(index.query_2(std::string("be"), 100)) == std::vector<std::uint64_t>{{2, 4}}));

    // Logical-position deletion removes only that record's composite range key
    // and prefix posting; the remaining duplicate is still queryable.
    index.erase_at(0);
    assert((ids(index.query_1(30, 30)) == std::vector<std::uint64_t>{{3}}));
    assert((ids(index.query_2(std::string("alpha"), 100)).empty()));
    assert((ids(index.query_2(std::string("al"), 100)) == std::vector<std::uint64_t>{{3}}));
    assert(index.query_0(3).size() == 1);
    return 0;
}}
''',
        encoding="utf-8",
    )

    binary = tmp_path / ("duplicate_semantics.exe" if os.name == "nt" or toolchain.kind == "msvc" else "duplicate_semantics")
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
