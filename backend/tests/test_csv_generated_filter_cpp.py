from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.artifact_codegen import generate_verified_header
from app.models import Assignment, CandidateResult, QueryKind, QuerySpec, FieldSpec, WorkloadSpec
from app.toolchain import base_environment, compile_command, discover_toolchain


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("primitive", ["ordered_tree", "sorted_array"])
def test_real_duplicate_preserving_filter_is_generated_compiled_and_executed(
    tmp_path: Path, primitive: str
) -> None:
    toolchain = discover_toolchain()
    if toolchain is None:
        pytest.skip("C++20 compiler not available in test environment")
    spec = WorkloadSpec(
        name="teacher_arbitrary_column",
        record_count=3,
        fields=[FieldSpec(name="Item_Category", type="string", cardinality=2)],
        queries=[QuerySpec(kind=QueryKind.FILTER, field="Item_Category", selectivity=0.67)],
    )
    selected = CandidateResult(
        id=f"test_{primitive}",
        assignments=[Assignment(query_index=0, query_kind=QueryKind.FILTER, field="Item_Category", primitive=primitive)],
        unique_primitives=[primitive],
        predicted_latency_us=1.0, predicted_memory_mb=0.001,
        predicted_build_ms=1.0, predicted_update_us=1.0, score=1.0, feasible=True,
    )
    header = generate_verified_header(spec, selected)
    (tmp_path / header.header_name).write_text(header.header_source, encoding="utf-8")
    source = tmp_path / "verify_filter.cpp"
    source.write_text(f'''#include "{header.header_name}"
#include <stdexcept>
#include <string>
int main() {{
    using Index = morpheus_generated::GeneratedIndex;
    Index idx;
    idx.insert(Index::Record{{"food"}});
    idx.insert(Index::Record{{"food"}});
    idx.insert(Index::Record{{"tools"}});
    if (idx.query_0(std::string("food")).size() != 2) return 1;
    idx.update_at(1, Index::Record{{"tools"}});
    if (idx.query_0(std::string("food")).size() != 1) return 2;
    if (idx.query_0(std::string("tools")).size() != 2) return 3;
    idx.erase_at(0);
    if (!idx.query_0(std::string("food")).empty()) return 4;
    if (idx.query_0(std::string("tools")).size() != 2) return 5;
    return 0;
}}
''', encoding="utf-8")
    target = tmp_path / ("verify_filter.exe" if toolchain.kind == "msvc" else "verify_filter")
    built = subprocess.run(
        compile_command(toolchain, source=source, output=target,
                        include_dirs=[ROOT / "core" / "include", tmp_path], optimize=False),
        cwd=tmp_path, env=base_environment(tmp_path),
        capture_output=True, text=True, timeout=120, check=False,
    )
    assert built.returncode == 0, built.stderr
    executed = subprocess.run([str(target)], cwd=tmp_path, env=base_environment(tmp_path),
                              capture_output=True, text=True, timeout=30, check=False)
    assert executed.returncode == 0, executed.stderr
