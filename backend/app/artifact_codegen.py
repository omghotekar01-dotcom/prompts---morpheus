from __future__ import annotations

import re
from dataclasses import dataclass

from .models import CandidateResult, QueryKind, WorkloadSpec


CPP_TYPES = {
    "uint64": "std::uint64_t",
    "uint64_t": "std::uint64_t",
    "uint32": "std::uint32_t",
    "uint32_t": "std::uint32_t",
    "int": "std::int64_t",
    "integer": "std::int64_t",
    "float": "double",
    "double": "double",
    "string": "std::string",
    "str": "std::string",
    "text": "std::string",
    "bool": "bool",
}

_CPP_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ArtifactCodegenError(ValueError):
    pass


@dataclass(frozen=True)
class GeneratedArtifact:
    header_name: str
    header_source: str
    candidate_id: str
    namespace_name: str = "morpheus_generated"


def _cpp_type(raw: str) -> str:
    return CPP_TYPES.get(raw.lower(), "std::string")


def _field_type(spec: WorkloadSpec, field_name: str) -> str:
    for field in spec.fields:
        if field.name == field_name:
            return _cpp_type(field.type)
    raise ArtifactCodegenError(f"unknown field {field_name!r}")


def _member_type(primitive: str, key_type: str | None = None) -> str:
    if primitive == "csr_graph":
        return "morpheus::CSRGraphIndex<std::uint32_t>"
    if key_type is None:
        raise ArtifactCodegenError(f"primitive {primitive!r} requires a physical key type")
    mapping = {
        "robin_hood_hash": f"morpheus::RobinHoodHashIndex<{key_type}, std::size_t>",
        "ordered_tree": f"morpheus::BPlusTreeIndex<{key_type}, std::size_t>",
        "sorted_array": f"morpheus::MutableSortedArrayIndex<{key_type}, std::size_t>",
        "radix_trie": "morpheus::MutablePrefixTrie<std::size_t>",
        "bitmap": f"morpheus::MutableBitmapFilterIndex<{key_type}, std::size_t>",
    }
    try:
        return mapping[primitive]
    except KeyError as exc:
        raise ArtifactCodegenError(
            f"P3 standalone code generation does not yet support primitive {primitive!r}"
        ) from exc


def _query_method(index: int, kind: QueryKind, member: str, key_type: str) -> str:
    if kind == QueryKind.POINT_LOOKUP:
        return f'''    [[nodiscard]] std::vector<Record> query_{index}(const {key_type}& value) const {{
        std::vector<Record> out;
        if (const auto* slot_id = {member}.find(value); slot_id != nullptr) {{
            append_live_record(*slot_id, out);
        }}
        return out;
    }}'''
    if kind == QueryKind.RANGE_SCAN:
        return f'''    [[nodiscard]] std::vector<Record> query_{index}(const {key_type}& low, const {key_type}& high) const {{
        std::vector<Record> out;
        for (const auto slot_id : {member}.range(low, high)) append_live_record(slot_id, out);
        return out;
    }}'''
    if kind == QueryKind.FILTER:
        return f'''    [[nodiscard]] std::vector<Record> query_{index}(const {key_type}& value) const {{
        std::vector<Record> out;
        for (const auto slot_id : {member}.filter(value)) append_live_record(slot_id, out);
        return out;
    }}'''
    if kind == QueryKind.PREFIX_SEARCH:
        return f'''    [[nodiscard]] std::vector<Record> query_{index}(const std::string& prefix, std::size_t limit = 100) const {{
        std::vector<Record> out;
        for (const auto slot_id : {member}.prefix_search(prefix, limit)) append_live_record(slot_id, out);
        return out;
    }}'''
    raise ArtifactCodegenError(f"P3 record query generation does not support {kind.value!r}")


def _graph_methods(index: int, member: str) -> str:
    return f'''    void configure_graph_{index}(
        std::size_t node_count,
        std::vector<std::pair<std::uint32_t, std::uint32_t>> edges,
        bool directed = true
    ) {{
        {member}.build(node_count, std::move(edges), directed);
    }}

    [[nodiscard]] std::vector<std::uint32_t> query_{index}(
        std::uint32_t start,
        std::size_t max_depth = std::numeric_limits<std::size_t>::max()
    ) const {{
        return {member}.bfs(start, max_depth);
    }}'''


def _winner_tracking_methods(
    index: int,
    member: str,
    tracking_member: str,
    key_type: str,
) -> str:
    """Maintain last-live-slot semantics without scanning the full record store.

    Stable slot IDs are monotonically assigned at insertion and preserve the
    logical insertion order used by the historical reverse live-order scan.
    Keeping each key's live slot IDs sorted therefore lets the physical unique
    index point at the same last-live winner while updates/deletes touch only the
    duplicate set for that key instead of O(total_records).
    """

    return f'''    void add_q{index}_slot(const {key_type}& key, std::size_t slot_id) {{
        auto& ids = {tracking_member}[key];
        const auto position = std::lower_bound(ids.begin(), ids.end(), slot_id);
        if (position == ids.end() || *position != slot_id) ids.insert(position, slot_id);
        {member}.insert_or_assign(key, ids.back());
    }}

    void remove_q{index}_slot(const {key_type}& key, std::size_t slot_id) {{
        const auto posting = {tracking_member}.find(key);
        if (posting == {tracking_member}.end()) throw std::runtime_error("MORPHEUS winner-slot invariant missing key");
        auto& ids = posting->second;
        const auto position = std::lower_bound(ids.begin(), ids.end(), slot_id);
        if (position == ids.end() || *position != slot_id) throw std::runtime_error("MORPHEUS winner-slot invariant missing slot");
        ids.erase(position);
        {member}.erase(key);
        if (ids.empty()) {{
            {tracking_member}.erase(posting);
        }} else {{
            {member}.insert_or_assign(key, ids.back());
        }}
    }}'''


def generate_verified_header(
    spec: WorkloadSpec,
    candidate: CandidateResult,
    *,
    namespace_name: str = "morpheus_generated",
) -> GeneratedArtifact:
    """Generate a standalone, compile-targeted C++ wrapper over the real P2 primitive library.

    Record-backed indexes store stable slot IDs rather than vector positions. Inserts update only the
    affected indexes; updates and deletes maintain per-key winner-slot postings for unique-key physical
    indexes instead of scanning the entire record store. Stable slot ordering preserves the historical
    last-live-duplicate-key semantics. Bitmap postings already retain all matching slot IDs. Logical
    record order is maintained separately from stable slots, while CSR graph topology remains isolated
    from ordinary record mutations.

    `namespace_name` is explicit so two generated candidate artifacts can coexist in one process during
    shadow migration. The default remains `morpheus_generated` for backwards compatibility with the
    single-artifact verification path.
    """

    if not _CPP_IDENTIFIER.fullmatch(namespace_name):
        raise ArtifactCodegenError("generated namespace must be a valid C++ identifier")

    fields = "\n".join(f"        {_cpp_type(field.type)} {field.name}{{}};" for field in spec.fields)

    members: list[str] = []
    methods: list[str] = []
    maintenance_helpers: list[str] = []
    insert_maintenance: list[str] = []
    update_maintenance: list[str] = []
    erase_maintenance: list[str] = []
    route_comments: list[str] = []

    for assignment in candidate.assignments:
        if assignment.query_kind in {QueryKind.INSERT, QueryKind.UPDATE, QueryKind.DELETE}:
            route_comments.append(
                f"// query[{assignment.query_index}] {assignment.query_kind.value}: handled by stable-slot mutation path"
            )
            continue

        member = f"q{assignment.query_index}_index_"
        if assignment.query_kind == QueryKind.GRAPH_TRAVERSAL:
            if assignment.primitive != "csr_graph":
                raise ArtifactCodegenError(
                    f"query[{assignment.query_index}] graph_traversal requires csr_graph, got {assignment.primitive!r}"
                )
            member_type = _member_type(assignment.primitive)
            members.append(f"    {member_type} {member};")
            methods.append(_graph_methods(assignment.query_index, member))
            route_comments.append(
                f"// query[{assignment.query_index}] graph_traversal(external topology) -> {assignment.primitive}"
            )
            continue

        if assignment.field is None:
            raise ArtifactCodegenError(
                f"query[{assignment.query_index}] {assignment.query_kind.value} requires a physical key field for P3 codegen"
            )
        field = assignment.field
        key_type = _field_type(spec, field)
        member_type = _member_type(assignment.primitive, key_type)
        members.append(f"    {member_type} {member};")
        methods.append(_query_method(assignment.query_index, assignment.query_kind, member, key_type))
        route_comments.append(
            f"// query[{assignment.query_index}] {assignment.query_kind.value}({field}) -> {assignment.primitive}"
        )

        if assignment.primitive == "bitmap":
            insert_maintenance.append(f"        {member}.add(record.{field}, slot_id);")
            update_maintenance.extend(
                [
                    f"        {member}.remove(before.{field}, slot_id);",
                    f"        {member}.add(after.{field}, slot_id);",
                ]
            )
            erase_maintenance.append(f"        {member}.remove(record.{field}, slot_id);")
        else:
            tracking_member = f"q{assignment.query_index}_winner_slots_"
            members.append(f"    std::map<{key_type}, std::vector<std::size_t>> {tracking_member};")
            maintenance_helpers.append(
                _winner_tracking_methods(
                    assignment.query_index,
                    member,
                    tracking_member,
                    key_type,
                )
            )
            insert_maintenance.append(f"        add_q{assignment.query_index}_slot(record.{field}, slot_id);")
            update_maintenance.extend(
                [
                    f"        remove_q{assignment.query_index}_slot(before.{field}, slot_id);",
                    f"        add_q{assignment.query_index}_slot(after.{field}, slot_id);",
                ]
            )
            erase_maintenance.append(f"        remove_q{assignment.query_index}_slot(record.{field}, slot_id);")

    if not members:
        raise ArtifactCodegenError("candidate has no queryable physical assignments for P3 code generation")

    header_name = f"morpheus_generated_{candidate.id}.hpp"
    source = f'''#pragma once
// MORPHEUS generated artifact — P3 stable-slot incremental-maintenance target
// Workload: {spec.name}
// Candidate: {candidate.id}
// Evidence state before external compile/differential test: GENERATED_NOT_VERIFIED

#include "morpheus/bplus_tree.hpp"
#include "morpheus/csr_graph.hpp"
#include "morpheus/mutable_indices.hpp"
#include "morpheus/structures.hpp"

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <map>
#include <optional>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace {namespace_name} {{

{chr(10).join(route_comments)}

class GeneratedIndex {{
public:
    struct Record {{
{fields}
        bool operator==(const Record&) const = default;
    }};

    void insert(const Record& record) {{
        const std::size_t slot_id = slots_.size();
        slots_.push_back(record);
        live_order_.push_back(slot_id);
{chr(10).join(insert_maintenance)}
        records_cache_dirty_ = true;
    }}

    void update_at(std::size_t position, const Record& record) {{
        const std::size_t slot_id = logical_slot(position);
        const Record before = slots_[slot_id].value();
        slots_[slot_id] = record;
        const Record& after = slots_[slot_id].value();
{chr(10).join(update_maintenance)}
        records_cache_dirty_ = true;
    }}

    void erase_at(std::size_t position) {{
        const std::size_t slot_id = logical_slot(position);
        const Record record = slots_[slot_id].value();
        slots_[slot_id].reset();
        live_order_.erase(live_order_.begin() + static_cast<std::ptrdiff_t>(position));
{chr(10).join(erase_maintenance)}
        records_cache_dirty_ = true;
    }}

    [[nodiscard]] const std::vector<Record>& records() const {{
        if (records_cache_dirty_) {{
            records_cache_.clear();
            records_cache_.reserve(live_order_.size());
            for (const auto slot_id : live_order_) {{
                if (slot_id < slots_.size() && slots_[slot_id].has_value()) records_cache_.push_back(slots_[slot_id].value());
            }}
            records_cache_dirty_ = false;
        }}
        return records_cache_;
    }}

    [[nodiscard]] std::size_t size() const noexcept {{ return live_order_.size(); }}
    [[nodiscard]] const char* candidate_id() const noexcept {{ return "{candidate.id}"; }}

{chr(10).join(methods)}

private:
    std::vector<std::optional<Record>> slots_;
    std::vector<std::size_t> live_order_;
    mutable std::vector<Record> records_cache_;
    mutable bool records_cache_dirty_ = true;
{chr(10).join(members)}

    [[nodiscard]] std::size_t logical_slot(std::size_t position) const {{
        if (position >= live_order_.size()) throw std::out_of_range("MORPHEUS logical record position");
        const auto slot_id = live_order_[position];
        if (slot_id >= slots_.size() || !slots_[slot_id].has_value()) throw std::runtime_error("MORPHEUS live-order invariant broken");
        return slot_id;
    }}

    void append_live_record(std::size_t slot_id, std::vector<Record>& out) const {{
        if (slot_id < slots_.size() && slots_[slot_id].has_value()) out.push_back(slots_[slot_id].value());
    }}

{chr(10).join(maintenance_helpers)}
}};

}}  // namespace {namespace_name}
'''
    return GeneratedArtifact(
        header_name=header_name,
        header_source=source,
        candidate_id=candidate.id,
        namespace_name=namespace_name,
    )