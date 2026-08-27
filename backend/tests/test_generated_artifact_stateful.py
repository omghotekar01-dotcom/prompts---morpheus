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
CORE_INCLUDE = REPO_ROOT / "core" / "include"

SPEC = """
version: mws-0.1
name: generated_stateful_differential
record_count: 1000
fields:
  - name: id
    type: uint64
    cardinality: 1000
  - name: name
    type: string
    cardinality: 1000
  - name: team
    type: string
    cardinality: 12
queries:
  - kind: point_lookup
    field: id
    weight: 0.34
  - kind: prefix_search
    field: name
    weight: 0.33
  - kind: filter
    field: team
    weight: 0.33
constraints:
  memory_mb: 64
objective:
  latency: 1.0
  memory: 0.1
  update: 0.2
  build: 0.05
"""


def test_generated_artifact_matches_reference_across_stateful_mutations(tmp_path: Path) -> None:
    compiler = shutil.which("g++") or shutil.which("clang++")
    if compiler is None:
        pytest.skip("C++20 compiler is unavailable in this environment")

    spec = parse_workload_text(SPEC)
    synthesis = synthesize(spec)
    assert synthesis.winner is not None
    artifact = generate_verified_header(spec, synthesis.winner)

    header = tmp_path / artifact.header_name
    header.write_text(artifact.header_source, encoding="utf-8")

    driver = tmp_path / "stateful_differential.cpp"
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
    std::vector<Record> reference;

    auto insert = [&](const Record& record) {{
        reference.push_back(record);
        index.insert(record);
    }};
    auto update = [&](std::size_t position, const Record& record) {{
        reference.at(position) = record;
        index.update_at(position, record);
    }};
    auto erase = [&](std::size_t position) {{
        reference.erase(reference.begin() + static_cast<std::ptrdiff_t>(position));
        index.erase_at(position);
    }};

    auto expected_point = [&](std::uint64_t id) {{
        std::vector<Record> out;
        for (const auto& record : reference) if (record.id == id) out = {{record}};
        return out;
    }};
    auto expected_team = [&](const std::string& team) {{
        std::vector<Record> out;
        for (const auto& record : reference) if (record.team == team) out.push_back(record);
        return out;
    }};
    auto expected_prefix = [&](const std::string& prefix) {{
        std::vector<Record> out;
        for (const auto& record : reference) {{
            if (record.name.rfind(prefix, 0) == 0) out.push_back(record);
        }}
        std::sort(out.begin(), out.end(), [](const Record& left, const Record& right) {{
            return left.name < right.name;
        }});
        return out;
    }};
    auto verify = [&]() {{
        assert(index.records() == reference);
        assert(index.query_0(1) == expected_point(1));
        assert(index.query_0(2) == expected_point(2));
        assert(index.query_0(4) == expected_point(4));
        assert(index.query_1("al") == expected_prefix("al"));
        assert(index.query_1("be") == expected_prefix("be"));
        assert(index.query_2("red") == expected_team("red"));
        assert(index.query_2("blue") == expected_team("blue"));
    }};

    insert(Record{{1, "alpha", "red"}});
    insert(Record{{2, "alpine", "blue"}});
    insert(Record{{3, "beta", "red"}});
    insert(Record{{4, "beacon", "blue"}});
    verify();

    update(1, Record{{2, "amber", "red"}});
    verify();

    erase(0);
    verify();

    insert(Record{{5, "algebra", "blue"}});
    update(1, Record{{4, "beryl", "red"}});
    verify();

    erase(reference.size() - 1);
    verify();
    return 0;
}}
''',
        encoding="utf-8",
    )

    binary = tmp_path / ("stateful_differential.exe" if os.name == "nt" else "stateful_differential")
    environment = os.environ.copy()
    environment["TMPDIR"] = str(tmp_path)
    environment["TMP"] = str(tmp_path)
    environment["TEMP"] = str(tmp_path)

    compile_process = subprocess.run(
        [
            compiler,
            "-std=c++20",
            "-O1",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
            "-I",
            str(CORE_INCLUDE),
            "-I",
            str(tmp_path),
            str(driver),
            "-o",
            str(binary),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
        cwd=tmp_path,
        env=environment,
    )
    assert compile_process.returncode == 0, compile_process.stderr

    run_process = subprocess.run(
        [str(binary)],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
        cwd=tmp_path,
        env=environment,
    )
    assert run_process.returncode == 0, run_process.stderr
