from __future__ import annotations

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


class ArtifactCodegenError(ValueError):
    pass


@dataclass(frozen=True)
class GeneratedArtifact:
    header_name: str
    header_source: str
    candidate_id: str


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


def _rebuild_statement(primitive: str, member: str, field: str) -> str:
    if primitive in {"robin_hood_hash", "ordered_tree", "sorted_array", "radix_trie"}:
        return f"            {member}.insert_or_assign(records_[i].{field}, i);"
    if primitive == "bitmap":
        return f"            {member}.add(records_[i].{field}, i);"
    raise ArtifactCodegenError(f"no record rebuild statement for {primitive!r}")


def _query_method(index: int, kind: QueryKind, member: str, key_type: str) -> str:
    if kind == QueryKind.POINT_LOOKUP:
        return f'''    [[nodiscard]] std::vector<Record> query_{index}(const {key_type}& value) const {{
        std::vector<Record> out;
        if (const auto* position = {member}.find(value); position != nullptr && *position < records_.size()) {{
            out.push_back(records_[*position]);
        }}
        return out;
    }}'''
    if kind == QueryKind.RANGE_SCAN:
        return f'''    [[nodiscard]] std::vector<Record> query_{index}(const {key_type}& low, const {key_type}& high) const {{
        std::vector<Record> out;
        for (const auto position : {member}.range(low, high)) {{
            if (position < records_.size()) out.push_back(records_[position]);
        }}
        return out;
    }}'''
    if kind == QueryKind.FILTER:
        return f'''    [[nodiscard]] std::vector<Record> query_{index}(const {key_type}& value) const {{
        std::vector<Record> out;
        for (const auto position : {member}.filter(value)) {{
            if (position < records_.size()) out.push_back(records_[position]);
        }}
        return out;
    }}'''
    if kind == QueryKind.PREFIX_SEARCH:
        return f'''    [[nodiscard]] std::vector<Record> query_{index}(const std::string& prefix, std::size_t limit = 100) const {{
        std::vector<Record> out;
        for (const auto position : {member}.prefix_search(prefix, limit)) {{
            if (position < records_.size()) out.push_back(records_[position]);
        }}
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


def generate_verified_header(spec: WorkloadSpec, candidate: CandidateResult) -> GeneratedArtifact:
    """Generate a standalone, compile-targeted C++ wrapper over the real P2 primitive library.

    Ordered-tree assignments use the incrementally rebalancing B+ tree primitive. Generated record
    mutations still rebuild record-backed indexes because vector row positions change after erasure.
    Mutable sorted-array, trie and bitmap adapters provide explicit deletion semantics for the next
    incremental-maintenance phase. CSR graph assignments are deliberately configured through a separate
    topology API because MWS graph-traversal queries do not claim graph edges are encoded in ordinary
    record fields; record rebuilds therefore preserve configured graph state.
    """

    fields = "\n".join(f"        {_cpp_type(field.type)} {field.name}{{}};" for field in spec.fields)

    members: list[str] = []
    resets: list[str] = []
    rebuilds: list[str] = []
    methods: list[str] = []
    route_comments: list[str] = []

    for assignment in candidate.assignments:
        if assignment.query_kind in {QueryKind.INSERT, QueryKind.UPDATE, QueryKind.DELETE}:
            route_comments.append(
                f"// query[{assignment.query_index}] {assignment.query_kind.value}: mutation handled by canonical record rebuild path"
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
        key_type = _field_type(spec, assignment.field)
        member_type = _member_type(assignment.primitive, key_type)
        members.append(f"    {member_type} {member};")
        resets.append(f"        {member} = {member_type}{{}};")
        rebuilds.append(_rebuild_statement(assignment.primitive, member, assignment.field))
        methods.append(_query_method(assignment.query_index, assignment.query_kind, member, key_type))
        route_comments.append(
            f"// query[{assignment.query_index}] {assignment.query_kind.value}({assignment.field}) -> {assignment.primitive}"
        )

    if not members:
        raise ArtifactCodegenError("candidate has no queryable physical assignments for P3 code generation")

    header_name = f"morpheus_generated_{candidate.id}.hpp"
    source = f'''#pragma once
// MORPHEUS generated artifact — P3 correctness-first target
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
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace morpheus_generated {{

{chr(10).join(route_comments)}

class GeneratedIndex {{
public:
    struct Record {{
{fields}
        bool operator==(const Record&) const = default;
    }};

    void insert(const Record& record) {{
        records_.push_back(record);
        rebuild_record_indices();
    }}

    void update_at(std::size_t position, const Record& record) {{
        if (position >= records_.size()) throw std::out_of_range("MORPHEUS update position");
        records_[position] = record;
        rebuild_record_indices();
    }}

    void erase_at(std::size_t position) {{
        if (position >= records_.size()) throw std::out_of_range("MORPHEUS erase position");
        records_.erase(records_.begin() + static_cast<std::ptrdiff_t>(position));
        rebuild_record_indices();
    }}

    [[nodiscard]] const std::vector<Record>& records() const noexcept {{ return records_; }}
    [[nodiscard]] const char* candidate_id() const noexcept {{ return "{candidate.id}"; }}

{chr(10).join(methods)}

private:
    std::vector<Record> records_;
{chr(10).join(members)}

    void rebuild_record_indices() {{
{chr(10).join(resets)}
        for (std::size_t i = 0; i < records_.size(); ++i) {{
{chr(10).join(rebuilds)}
        }}
    }}
}};

}}  // namespace morpheus_generated
'''
    return GeneratedArtifact(header_name=header_name, header_source=source, candidate_id=candidate.id)
