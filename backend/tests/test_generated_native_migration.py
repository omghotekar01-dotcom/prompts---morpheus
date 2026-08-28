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


def _different_feasible_candidate(synthesis):
    assert synthesis.winner is not None
    winner_signature = tuple(
        (item.query_index, item.query_kind.value, item.field, item.primitive)
        for item in synthesis.winner.assignments
    )
    for candidate in synthesis.candidates:
        if not candidate.feasible or candidate.id == synthesis.winner.id:
            continue
        signature = tuple(
            (item.query_index, item.query_kind.value, item.field, item.primitive)
            for item in candidate.assignments
        )
        if signature != winner_signature:
            return candidate
    raise AssertionError("users-demo synthesis did not expose a distinct feasible configuration")


def test_real_generated_candidates_migrate_publish_and_rollback(tmp_path: Path) -> None:
    """Close the P7 generated-object/native-publication integration gap.

    This test does not use hand-written stand-in indexes: both C++ payload types
    are emitted by the MORPHEUS code generator from two distinct feasible
    physical configurations for the same workload. Logical records are copied
    into the target configuration, semantically shadow-validated, atomically
    published through ErasedVersionedSlot, queried, and then rolled back to the
    exact prior generated payload.
    """

    toolchain = discover_toolchain()
    if toolchain is None:
        pytest.skip("C++20 compiler is unavailable in this environment")

    spec = parse_workload_text(EXAMPLE.read_text(encoding="utf-8"))
    synthesis = synthesize(spec)
    assert synthesis.winner is not None
    alternative = _different_feasible_candidate(synthesis)

    source_artifact = generate_verified_header(
        spec,
        synthesis.winner,
        namespace_name="morpheus_live_source",
    )
    target_artifact = generate_verified_header(
        spec,
        alternative,
        namespace_name="morpheus_live_target",
    )
    assert source_artifact.candidate_id != target_artifact.candidate_id

    source_header = tmp_path / "candidate_source.hpp"
    target_header = tmp_path / "candidate_target.hpp"
    source_header.write_text(source_artifact.header_source, encoding="utf-8")
    target_header.write_text(target_artifact.header_source, encoding="utf-8")

    driver = tmp_path / "generated_native_migration.cpp"
    driver.write_text(
        f'''#include "candidate_source.hpp"
#include "candidate_target.hpp"
#include "morpheus/migration_publish.hpp"

#include <cassert>
#include <cstdint>
#include <memory>
#include <string>
#include <typeindex>
#include <typeinfo>

int main() {{
    using Source = morpheus_live_source::GeneratedIndex;
    using Target = morpheus_live_target::GeneratedIndex;

    auto source_mutable = std::make_shared<Source>();
    source_mutable->insert(Source::Record{{1, 24, "Pune"}});
    source_mutable->insert(Source::Record{{2, 29, "Pune"}});
    source_mutable->insert(Source::Record{{3, 42, "Nashik"}});
    source_mutable->insert(Source::Record{{4, 36, "Mumbai"}});
    const std::shared_ptr<const Source> source = source_mutable;

    morpheus::ErasedVersionedSlot slot("{source_artifact.candidate_id}", source);
    const auto source_version = slot.lease();
    assert(source_version->generation == 1);
    assert(source_version->payload_type == std::type_index(typeid(Source)));

    const auto generation_two = morpheus::migrate_validate_and_activate<Source, Target>(
        slot,
        source_version,
        "{target_artifact.candidate_id}",
        *source,
        [](const Source::Record& record) {{
            return Target::Record{{record.id, record.age, record.city}};
        }},
        [](const Target& candidate) {{
            return candidate.size() == 4
                && candidate.query_0(2).size() == 1
                && candidate.query_1(20, 30).size() == 2
                && candidate.query_2(std::string("Pune")).size() == 2;
        }}
    );

    assert(generation_two == 2);
    const auto target_version = slot.lease();
    assert(target_version->candidate_id == "{target_artifact.candidate_id}");
    assert(target_version->payload_type == std::type_index(typeid(Target)));
    const auto target = slot.lease_as<Target>();
    assert(target->size() == source->size());
    assert(target->query_0(2).size() == source->query_0(2).size());
    assert(target->query_1(20, 30).size() == source->query_1(20, 30).size());
    assert(target->query_2(std::string("Pune")).size() == source->query_2(std::string("Pune")).size());

    // A stale source lease cannot publish a second shadow after the active
    // generation changed, even if its old payload remains alive for readers.
    bool stale_publish_rejected = false;
    try {{
        (void)morpheus::migrate_validate_and_activate<Source, Target>(
            slot,
            source_version,
            "stale-target",
            *source,
            [](const Source::Record& record) {{
                return Target::Record{{record.id, record.age, record.city}};
            }},
            [](const Target&) {{ return true; }}
        );
    }} catch (const std::runtime_error&) {{
        stale_publish_rejected = true;
    }}
    assert(stale_publish_rejected);

    const auto generation_three = slot.rollback(target_version);
    assert(generation_three == 3);
    const auto restored_version = slot.lease();
    assert(restored_version->candidate_id == "{source_artifact.candidate_id}");
    assert(restored_version->payload_type == std::type_index(typeid(Source)));
    const auto restored = slot.lease_as<Source>();
    assert(restored.get() == source.get());
    assert(restored->query_0(3).size() == 1);
    assert(restored->query_2(std::string("Mumbai")).size() == 1);

    // Re-publish from the exact restored lease, then intentionally retire the
    // rollback payload only after accepting the new generation as stable.
    const auto generation_four = morpheus::migrate_validate_and_activate<Source, Target>(
        slot,
        restored_version,
        "{target_artifact.candidate_id}",
        *restored,
        [](const Source::Record& record) {{
            return Target::Record{{record.id, record.age, record.city}};
        }},
        [](const Target& candidate) {{ return candidate.size() == 4; }}
    );
    assert(generation_four == 4);
    const auto stable_target = slot.lease();
    assert(slot.retire_rollback_history(stable_target) == 1);
    assert(slot.rollback_depth() == 0);
    return 0;
}}
''',
        encoding="utf-8",
    )

    binary = tmp_path / ("generated_native_migration.exe" if os.name == "nt" or toolchain.kind == "msvc" else "generated_native_migration")
    command = compile_command(
        toolchain,
        source=driver,
        output=binary,
        include_dirs=[CORE_INCLUDE, tmp_path],
        optimize=False,
    )
    compiled = subprocess.run(
        command,
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
