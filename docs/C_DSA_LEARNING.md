# C DSA learning example

The MORPHEUS native optimizer and data-structure implementations use C++20;
the candidate scorer is Java 17+. This small C11 module adds a runnable,
tested example of binary search without changing those production roles.

## What binary search teaches

Binary search works on an ascending sorted array. Each comparison discards
about half of the remaining range, so searching `n` values takes
**O(log n)** comparisons and **O(1)** extra space. The sorted-input requirement
is part of the algorithm's contract; the demo checks it before searching.
When values repeat, the implementation returns the first matching index.

## Build and run

From the repository root, configure and build the C targets with CMake:

```powershell
cmake -S core -B build\c-dsa
cmake --build build\c-dsa --config Release --target morpheus_c_binary_search morpheus_c_dsa_tests
ctest --test-dir build\c-dsa -C Release -R morpheus_c_dsa_tests --output-on-failure
```

Give the program a target followed by the actual sorted integers to search:

```powershell
.\build\c-dsa\Release\morpheus_c_binary_search.exe 8 1 4 8 12
```

The result is calculated from those arguments. Unsorted values and invalid
integers are rejected instead of silently producing a misleading answer.

If CMake selects an incomplete Visual Studio installation even though GCC is
available on `PATH`, compile the small lesson directly:

```powershell
New-Item -ItemType Directory -Force build\c-dsa-demo | Out-Null
gcc -std=c11 -pedantic-errors -Wall -Wextra -Wpedantic -Werror -I core\include core\src\binary_search.c core\src\c_binary_search_demo.c -o build\c-dsa-demo\morpheus_c_binary_search.exe
.\build\c-dsa-demo\morpheus_c_binary_search.exe 8 1 4 8 12
```

The equivalent test command compiles `core\tests\test_binary_search.c` with
`core\src\binary_search.c` and runs the resulting executable.

The reusable C API is in `core/include/morpheus/binary_search.h`; its
implementation and focused edge-case tests are in `core/src/binary_search.c`
and `core/tests/test_binary_search.c`. The library assumes its caller has
already established sorted order so the search itself stays O(log n).
