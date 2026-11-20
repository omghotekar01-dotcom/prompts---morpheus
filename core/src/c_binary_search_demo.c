#include "morpheus/binary_search.h"

#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>

static int parse_int(const char *text, int *value)
{
    char *end = NULL;
    long parsed;

    errno = 0;
    parsed = strtol(text, &end, 10);
    if (text[0] == '\0' || end == text || *end != '\0'
        || errno == ERANGE || parsed < INT_MIN || parsed > INT_MAX) {
        return 0;
    }
    *value = (int)parsed;
    return 1;
}

int main(int argc, char **argv)
{
    int target;
    int *values;
    size_t count;
    size_t index = 0;
    int i;
    morpheus_search_status result;

    if (argc < 3) {
        fprintf(stderr, "Usage: %s <target> <sorted integer> [sorted integer...]\n", argv[0]);
        return 2;
    }
    if (!parse_int(argv[1], &target)) {
        fprintf(stderr, "Invalid target integer: %s\n", argv[1]);
        return 2;
    }

    count = (size_t)(argc - 2);
    if (count > (size_t)-1 / sizeof(*values)) {
        fprintf(stderr, "Input array is too large.\n");
        return 2;
    }
    values = (int *)malloc(count * sizeof(*values));
    if (values == NULL) {
        fprintf(stderr, "Could not allocate the input array.\n");
        return 2;
    }

    for (i = 0; i < argc - 2; ++i) {
        if (!parse_int(argv[i + 2], &values[i])) {
            fprintf(stderr, "Invalid array integer: %s\n", argv[i + 2]);
            free(values);
            return 2;
        }
        if (i > 0 && values[i - 1] > values[i]) {
            fprintf(stderr, "Array values must be sorted in ascending order.\n");
            free(values);
            return 2;
        }
    }

    result = morpheus_binary_search_int(values, count, target, &index);
    free(values);

    if (result == MORPHEUS_SEARCH_FOUND) {
        printf("Found %d at index %zu.\n", target, index);
        return 0;
    }
    if (result == MORPHEUS_SEARCH_NOT_FOUND) {
        printf("%d was not found.\n", target);
        return 1;
    }
    fprintf(stderr, "Invalid input to binary search.\n");
    return 2;
}
