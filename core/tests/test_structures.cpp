#include "morpheus/structures.hpp"

#include <cassert>
#include <cstdint>
#include <iostream>
#include <string>
#include <vector>

using morpheus::BitmapFilterIndex;
using morpheus::OrderedTreeIndex;
using morpheus::PrefixTrie;
using morpheus::RobinHoodHashIndex;
using morpheus::SortedArrayIndex;

int main() {
    {
        RobinHoodHashIndex<std::uint64_t, std::string> index(8);
        for (std::uint64_t i = 0; i < 500; ++i) index.insert_or_assign(i, "v" + std::to_string(i));
        assert(index.size() == 500);
        assert(index.find(42) && *index.find(42) == "v42");
        index.insert_or_assign(42, "updated");
        assert(*index.find(42) == "updated");
        assert(index.erase(42));
        assert(index.find(42) == nullptr);
        assert(!index.erase(42));
        for (std::uint64_t i = 0; i < 500; ++i) {
            if (i == 42) continue;
            assert(index.find(i) != nullptr);
        }
    }

    {
        OrderedTreeIndex<int, std::string> index;
        index.insert_or_assign(10, "a");
        index.insert_or_assign(20, "b");
        index.insert_or_assign(30, "c");
        auto values = index.range(15, 30);
        assert((values == std::vector<std::string>{"b", "c"}));
        assert(index.find(20) && *index.find(20) == "b");
        assert(index.erase(20));
        assert(index.find(20) == nullptr);
    }

    {
        SortedArrayIndex<int, std::string> index;
        index.bulk_load({{30, "c"}, {10, "a"}, {20, "b"}});
        assert(index.find(10) && *index.find(10) == "a");
        auto values = index.range(10, 20);
        assert((values == std::vector<std::string>{"a", "b"}));
        index.insert_or_assign(15, "x");
        assert(index.find(15) && *index.find(15) == "x");
    }

    {
        PrefixTrie<int> trie;
        trie.insert_or_assign("apple", 1);
        trie.insert_or_assign("app", 2);
        trie.insert_or_assign("apricot", 3);
        trie.insert_or_assign("banana", 4);
        assert(trie.find("apple") && *trie.find("apple") == 1);
        auto matches = trie.prefix_search("ap", 10);
        assert(matches.size() == 3);
        auto limited = trie.prefix_search("ap", 2);
        assert(limited.size() == 2);
    }

    {
        BitmapFilterIndex<std::string> index;
        index.add("pune", 1);
        index.add("pune", 2);
        index.add("nashik", 3);
        assert((index.filter("pune") == std::vector<std::uint32_t>{1, 2}));
        assert(index.remove("pune", 1));
        assert((index.filter("pune") == std::vector<std::uint32_t>{2}));
    }

    std::cout << "MORPHEUS primitive tests passed\n";
    return 0;
}
