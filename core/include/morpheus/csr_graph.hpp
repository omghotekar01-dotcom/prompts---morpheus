#pragma once

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <deque>
#include <limits>
#include <span>
#include <stdexcept>
#include <utility>
#include <vector>

namespace morpheus {

// Read-optimized compressed sparse row graph primitive.
// Build is explicit and deterministic; adjacency lists are sorted/deduplicated.
// Dynamic edge mutation intentionally requires rebuild so the capability truth
// matches the read-mostly CSR model used by the synthesis catalog.
template <typename NodeId = std::uint32_t>
class CSRGraphIndex {
public:
    using edge_type = std::pair<NodeId, NodeId>;

    void build(std::size_t node_count, std::vector<edge_type> edges, bool directed = true) {
        if (node_count > static_cast<std::size_t>(std::numeric_limits<NodeId>::max())) {
            throw std::invalid_argument("node_count exceeds NodeId range");
        }

        std::vector<std::vector<NodeId>> adjacency(node_count);
        for (const auto& [from, to] : edges) {
            const auto from_index = static_cast<std::size_t>(from);
            const auto to_index = static_cast<std::size_t>(to);
            if (from_index >= node_count || to_index >= node_count) {
                throw std::out_of_range("CSR edge references node outside declared node_count");
            }
            adjacency[from_index].push_back(to);
            if (!directed && from != to) adjacency[to_index].push_back(from);
        }

        offsets_.assign(node_count + 1, 0);
        neighbors_.clear();
        for (std::size_t node = 0; node < node_count; ++node) {
            auto& row = adjacency[node];
            std::sort(row.begin(), row.end());
            row.erase(std::unique(row.begin(), row.end()), row.end());
            offsets_[node + 1] = offsets_[node] + row.size();
            neighbors_.insert(neighbors_.end(), row.begin(), row.end());
        }
        directed_ = directed;
    }

    [[nodiscard]] std::size_t node_count() const noexcept {
        return offsets_.empty() ? 0 : offsets_.size() - 1;
    }

    [[nodiscard]] std::size_t edge_count() const noexcept { return neighbors_.size(); }
    [[nodiscard]] bool directed() const noexcept { return directed_; }

    [[nodiscard]] std::span<const NodeId> neighbors(NodeId node) const {
        const auto index = static_cast<std::size_t>(node);
        if (index >= node_count()) throw std::out_of_range("CSR node outside graph");
        const auto begin = offsets_[index];
        const auto end = offsets_[index + 1];
        return std::span<const NodeId>(neighbors_.data() + begin, end - begin);
    }

    [[nodiscard]] bool contains_edge(NodeId from, NodeId to) const {
        const auto row = neighbors(from);
        return std::binary_search(row.begin(), row.end(), to);
    }

    [[nodiscard]] std::vector<NodeId> bfs(NodeId start, std::size_t max_depth = std::numeric_limits<std::size_t>::max()) const {
        const auto start_index = static_cast<std::size_t>(start);
        if (start_index >= node_count()) throw std::out_of_range("CSR BFS start outside graph");

        std::vector<NodeId> order;
        std::vector<bool> visited(node_count(), false);
        std::deque<std::pair<NodeId, std::size_t>> queue;
        visited[start_index] = true;
        queue.emplace_back(start, 0);

        while (!queue.empty()) {
            const auto [node, depth] = queue.front();
            queue.pop_front();
            order.push_back(node);
            if (depth >= max_depth) continue;
            for (const NodeId next : neighbors(node)) {
                const auto next_index = static_cast<std::size_t>(next);
                if (!visited[next_index]) {
                    visited[next_index] = true;
                    queue.emplace_back(next, depth + 1);
                }
            }
        }
        return order;
    }

    [[nodiscard]] bool validate() const noexcept {
        if (offsets_.empty()) return neighbors_.empty();
        if (offsets_.front() != 0 || offsets_.back() != neighbors_.size()) return false;
        for (std::size_t i = 1; i < offsets_.size(); ++i) {
            if (offsets_[i] < offsets_[i - 1] || offsets_[i] > neighbors_.size()) return false;
        }
        const auto n = node_count();
        for (std::size_t node = 0; node < n; ++node) {
            const auto begin = offsets_[node];
            const auto end = offsets_[node + 1];
            if (!std::is_sorted(neighbors_.begin() + static_cast<std::ptrdiff_t>(begin), neighbors_.begin() + static_cast<std::ptrdiff_t>(end))) {
                return false;
            }
            for (std::size_t i = begin; i < end; ++i) {
                if (static_cast<std::size_t>(neighbors_[i]) >= n) return false;
                if (i > begin && neighbors_[i - 1] == neighbors_[i]) return false;
            }
        }
        return true;
    }

private:
    std::vector<std::size_t> offsets_;
    std::vector<NodeId> neighbors_;
    bool directed_ = true;
};

}  // namespace morpheus
