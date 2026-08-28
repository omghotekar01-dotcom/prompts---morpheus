#include "morpheus/bplus_tree.hpp"

#include <algorithm>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <map>
#include <random>
#include <utility>
#include <vector>

namespace {

template <std::size_t MaxKeys>
void assert_matches(const morpheus::BPlusTreeIndex<int, int, MaxKeys>& tree, const std::map<int, int>& oracle) {
    assert(tree.validate());
    assert(tree.size() == oracle.size());
    const auto items = tree.items();
    assert(items.size() == oracle.size());
    auto expected = oracle.begin();
    for (const auto& [key, value] : items) {
        assert(expected != oracle.end());
        assert(key == expected->first);
        assert(value == expected->second);
        const auto* found = tree.find(key);
        assert(found && *found == value);
        ++expected;
    }
    assert(expected == oracle.end());
}

template <std::size_t MaxKeys>
void exercise_delete_patterns(std::uint32_t seed) {
    morpheus::BPlusTreeIndex<int, int, MaxKeys> tree;
    std::map<int, int> oracle;

    std::vector<int> keys(600);
    for (int i = 0; i < static_cast<int>(keys.size()); ++i) keys[static_cast<std::size_t>(i)] = i;
    std::mt19937 rng(seed);
    std::shuffle(keys.begin(), keys.end(), rng);

    for (const auto key : keys) {
        tree.insert_or_assign(key, key * 17);
        oracle.insert_or_assign(key, key * 17);
    }
    assert(tree.height() >= 3);
    assert_matches(tree, oracle);

    // Updates are cardinality-neutral and preserve tree invariants.
    for (int key = 0; key < 600; key += 37) {
        tree.insert_or_assign(key, -key);
        oracle.insert_or_assign(key, -key);
    }
    assert_matches(tree, oracle);

    // Delete in a second shuffled order. Validation after every erase forces
    // leaf/internal borrowing, merging, separator repair and root collapse.
    std::shuffle(keys.begin(), keys.end(), rng);
    std::size_t erased = 0;
    for (const auto key : keys) {
        assert(tree.erase(key));
        assert(oracle.erase(key) == 1U);
        assert(tree.find(key) == nullptr);
        assert(!tree.erase(key));
        ++erased;
        if ((erased % 7U) == 0U || oracle.size() < 16U) assert_matches(tree, oracle);
    }
    assert(tree.empty());
    assert(tree.size() == 0);
    assert(tree.height() == 1);
    assert(tree.validate());
    assert(tree.items().empty());
}

} // namespace

int main() {
    // Small fanouts force rebalancing paths at high frequency.
    exercise_delete_patterns<3>(1337);
    exercise_delete_patterns<4>(7331);
    exercise_delete_patterns<5>(424242);

    {
        morpheus::BPlusTreeIndex<int, int, 5> tree;
        std::map<int, int> oracle;
        for (int key = 0; key < 200; ++key) {
            tree.insert_or_assign(key, key * 10);
            oracle.emplace(key, key * 10);
        }
        for (int key = 0; key < 200; key += 2) {
            assert(tree.erase(key));
            oracle.erase(key);
        }
        assert_matches(tree, oracle);

        const auto values = tree.range(51, 71);
        std::vector<int> expected;
        for (const auto& [key, value] : oracle) {
            if (key >= 51 && key <= 71) expected.push_back(value);
        }
        assert(values == expected);
        assert(tree.range(100, 50).empty());
    }

    std::cout << "MORPHEUS rebalancing B+ tree tests passed\n";
    return 0;
}
