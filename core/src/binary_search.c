#include "morpheus/binary_search.h"

morpheus_search_status morpheus_binary_search_int(
    const int *sorted_values,
    size_t count,
    int target,
    size_t *out_index)
{
    size_t first = 0;
    size_t last = count;

    if (out_index == NULL || (count > 0 && sorted_values == NULL)) {
        return MORPHEUS_SEARCH_INVALID_ARGUMENT;
    }

    while (first < last) {
        const size_t middle = first + (last - first) / 2;
        if (sorted_values[middle] < target) {
            first = middle + 1;
        } else {
            last = middle;
        }
    }

    if (first < count && sorted_values[first] == target) {
        *out_index = first;
        return MORPHEUS_SEARCH_FOUND;
    }
    return MORPHEUS_SEARCH_NOT_FOUND;
}
