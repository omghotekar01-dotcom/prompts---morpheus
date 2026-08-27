#include "morpheus/compressed_bitmap.hpp"

#include <cassert>
#include <cstdint>
#include <iostream>
#include <string>
#include <vector>

using morpheus::CompressedBitmap;
using morpheus::CompressedBitmapFilterIndex;

int main() {
    {
        CompressedBitmap<std::uint32_t> bitmap;
        assert(bitmap.add(1));
        assert(bitmap.add(2));
        assert(bitmap.add(65535));
        assert(bitmap.add(65536));
        assert(bitmap.add(70000));
        assert(!bitmap.add(2));
        assert(bitmap.size() == 5);
        assert(bitmap.container_count() == 2);
        assert(bitmap.contains(65536));
        assert(!bitmap.contains(999));
        assert((bitmap.values() == std::vector<std::uint32_t>{1, 2, 65535, 65536, 70000}));
        assert(bitmap.remove(2));
        assert(!bitmap.remove(2));
        assert((bitmap.values() == std::vector<std::uint32_t>{1, 65535, 65536, 70000}));
    }

    {
        CompressedBitmap<std::uint32_t> left;
        CompressedBitmap<std::uint32_t> right;
        for (auto id : {1U, 2U, 3U, 65536U, 70000U}) left.add(id);
        for (auto id : {2U, 3U, 4U, 65536U, 80000U}) right.add(id);
        assert((left.intersection(right).values() == std::vector<std::uint32_t>{2, 3, 65536}));
        const auto united = left.set_union(right);
        assert((united.values() == std::vector<std::uint32_t>{1, 2, 3, 4, 65536, 70000, 80000}));
        assert(united.size() == 7);
        assert(united.container_count() == 2);
        assert((right.set_union(left).values() == united.values()));

        CompressedBitmap<std::uint32_t> disjoint;
        disjoint.add(3U << 16U);
        disjoint.add((3U << 16U) + 9U);
        const auto expanded = united.set_union(disjoint);
        assert(expanded.size() == 9);
        assert(expanded.container_count() == 3);
        assert(expanded.contains(3U << 16U));
        assert(expanded.contains((3U << 16U) + 9U));
        assert((united.set_union({}).values() == united.values()));
    }

    {
        CompressedBitmap<std::uint32_t> empty;
        CompressedBitmap<std::uint32_t> populated;
        populated.add(42);
        populated.add(1U << 16U);
        assert(empty.set_union(populated).values() == populated.values());
        assert(populated.set_union(empty).values() == populated.values());
        assert(empty.intersection(populated).empty());
    }

    {
        CompressedBitmapFilterIndex<std::string> index;
        index.add("pune", 1);
        index.add("pune", 2);
        index.add("student", 2);
        index.add("student", 3);
        assert(index.contains("pune", 1));
        assert((index.filter("pune") == std::vector<std::uint32_t>{1, 2}));
        assert((index.filter_all("pune", "student") == std::vector<std::uint32_t>{2}));
        assert(index.remove("pune", 1));
        assert((index.filter("pune") == std::vector<std::uint32_t>{2}));
    }

    std::cout << "MORPHEUS compressed bitmap tests passed\n";
    return 0;
}
