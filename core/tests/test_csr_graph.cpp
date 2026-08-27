#include "morpheus/csr_graph.hpp"

#include <cassert>
#include <cstdint>
#include <stdexcept>
#include <vector>

int main() {
    using Graph = morpheus::CSRGraphIndex<std::uint32_t>;

    Graph graph;
    graph.build(
        6,
        {
            {0, 1}, {0, 2}, {1, 3}, {2, 3}, {3, 4}, {4, 5},
            {0, 2},  // duplicate is deterministically removed
        },
        true
    );

    assert(graph.validate());
    assert(graph.node_count() == 6);
    assert(graph.edge_count() == 6);
    assert(graph.directed());
    assert(graph.contains_edge(0, 1));
    assert(graph.contains_edge(0, 2));
    assert(!graph.contains_edge(2, 0));

    const auto row = graph.neighbors(0);
    assert(row.size() == 2);
    assert(row[0] == 1);
    assert(row[1] == 2);

    const auto depth_one = graph.bfs(0, 1);
    assert((depth_one == std::vector<std::uint32_t>{0, 1, 2}));

    const auto all = graph.bfs(0);
    assert((all == std::vector<std::uint32_t>{0, 1, 2, 3, 4, 5}));

    Graph undirected;
    undirected.build(3, {{0, 1}, {1, 2}}, false);
    assert(undirected.validate());
    assert(!undirected.directed());
    assert(undirected.contains_edge(1, 0));
    assert(undirected.contains_edge(2, 1));
    assert(undirected.edge_count() == 4);

    bool invalid_edge_rejected = false;
    try {
        Graph invalid;
        invalid.build(2, {{0, 2}}, true);
    } catch (const std::out_of_range&) {
        invalid_edge_rejected = true;
    }
    assert(invalid_edge_rejected);

    return 0;
}
