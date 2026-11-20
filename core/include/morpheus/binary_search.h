#ifndef MORPHEUS_BINARY_SEARCH_H
#define MORPHEUS_BINARY_SEARCH_H

#include <stddef.h>

typedef enum morpheus_search_status {
    MORPHEUS_SEARCH_INVALID_ARGUMENT = -1,
    MORPHEUS_SEARCH_NOT_FOUND = 0,
    MORPHEUS_SEARCH_FOUND = 1
} morpheus_search_status;

/*
 * Searches ascending sorted_values and returns the first matching index.
 * The array must be sorted in nondecreasing order. On NOT_FOUND, out_index
 * is left unchanged. A null array is valid only when count is zero.
 */
morpheus_search_status morpheus_binary_search_int(
    const int *sorted_values,
    size_t count,
    int target,
    size_t *out_index);

#endif
