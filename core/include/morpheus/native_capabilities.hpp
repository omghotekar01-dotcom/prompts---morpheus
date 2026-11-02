#pragma once
// C++20 DSA operation eligibility. Fixed implemented capabilities != hardcoded answers.
#include <algorithm>
#include <array>
#include <cstddef>
#include <stdexcept>
#include <string>
#include <string_view>

namespace morpheus::capability {
struct Request {
    std::size_t rows = 0;
    std::string operation;
    std::string field_type;
    std::size_t cardinality = 0;
};
struct Rule {
    std::string_view name;
    std::string_view operations;
};
inline constexpr std::array<Rule, 6> implemented{{
    {"robin_hood_hash", "point_lookup,insert,update,delete"},
    {"sorted_array", "point_lookup,range_scan,filter"},
    {"ordered_tree", "point_lookup,range_scan,filter,insert,update,delete"},
    {"radix_trie", "point_lookup,prefix_search"},
    {"bitmap", "filter"},
    {"csr_graph", "graph_traversal"},
}};
enum class Verdict { eligible, unsupported_operation, incompatible_type, excessive_cardinality };
inline bool supports(std::string_view supported, std::string_view target) {
    for (std::size_t begin = 0; begin < supported.size();) {
        const std::size_t end = supported.find(',', begin);
        const auto candidate = supported.substr(begin, end == std::string_view::npos
            ? supported.size() - begin : end - begin);
        if (candidate == target) return true;
        if (end == std::string_view::npos) break;
        begin = end + 1;
    }
    return false;
}
inline bool is_string_field(const std::string& type) {
    return type.find("str") != std::string::npos ||
           type.find("text") != std::string::npos ||
           type.find("char") != std::string::npos;
}
inline Verdict check(const Rule& primitive, const Request& request) {
    if (request.rows < 1 || request.operation.empty() ||
        request.cardinality > request.rows)
        throw std::invalid_argument("invalid native capability workload");
    if (!supports(primitive.operations, request.operation))
        return Verdict::unsupported_operation;
    if (primitive.name == "radix_trie" && !request.field_type.empty() &&
        !is_string_field(request.field_type))
        return Verdict::incompatible_type;
    if (primitive.name == "bitmap" && request.cardinality > 0 &&
        request.cardinality > std::max<std::size_t>(100000, request.rows / 3))
        return Verdict::excessive_cardinality;
    return Verdict::eligible;
}
inline std::string_view verdict_name(Verdict verdict) {
    switch (verdict) {
        case Verdict::eligible: return "eligible";
        case Verdict::unsupported_operation: return "unsupported_operation";
        case Verdict::incompatible_type: return "incompatible_type";
        case Verdict::excessive_cardinality: return "excessive_cardinality";
    }
    throw std::invalid_argument("unknown capability verdict");
}
} // namespace morpheus::capability
