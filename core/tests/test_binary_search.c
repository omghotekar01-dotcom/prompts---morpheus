#include "morpheus/binary_search.h"

#include <limits.h>
#include <stdio.h>

static int check(int condition, const char *message)
{
    if (!condition) {
        fprintf(stderr, "FAIL: %s\n", message);
        return 0;
    }
    return 1;
}

int main(void)
{
    const int values[] = {INT_MIN, -3, 0, 4, 4, 4, INT_MAX};
    size_t index = 42;
    int passed = 1;

    passed &= check(
        morpheus_binary_search_int(values, 7, INT_MIN, &index) == MORPHEUS_SEARCH_FOUND
            && index == 0,
        "find the first array element");
    passed &= check(
        morpheus_binary_search_int(values, 7, 4, &index) == MORPHEUS_SEARCH_FOUND
            && index == 3,
        "return the first matching duplicate");
    passed &= check(
        morpheus_binary_search_int(values, 7, INT_MAX, &index) == MORPHEUS_SEARCH_FOUND
            && index == 6,
        "find the last array element");
    index = 42;
    passed &= check(
        morpheus_binary_search_int(values, 7, 5, &index) == MORPHEUS_SEARCH_NOT_FOUND
            && index == 42,
        "leave the output index unchanged when absent");
    passed &= check(
        morpheus_binary_search_int(NULL, 0, 1, &index) == MORPHEUS_SEARCH_NOT_FOUND,
        "search an empty array");
    passed &= check(
        morpheus_binary_search_int(NULL, 1, 1, &index) == MORPHEUS_SEARCH_INVALID_ARGUMENT,
        "reject a null nonempty array");
    passed &= check(
        morpheus_binary_search_int(values, 7, 1, NULL) == MORPHEUS_SEARCH_INVALID_ARGUMENT,
        "reject a null output index");

    if (!passed) {
        return 1;
    }
    puts("C_BINARY_SEARCH_TESTS_PASS");
    return 0;
}
