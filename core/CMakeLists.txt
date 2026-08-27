cmake_minimum_required(VERSION 3.20)
project(morpheus_core LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(MORPHEUS_ENABLE_SANITIZERS "Enable AddressSanitizer and UndefinedBehaviorSanitizer on supported toolchains" OFF)

find_package(Threads REQUIRED)

add_library(morpheus_core INTERFACE)
target_include_directories(morpheus_core INTERFACE ${CMAKE_CURRENT_SOURCE_DIR}/include)

if(MSVC)
  target_compile_options(morpheus_core INTERFACE /W4 /permissive-)
else()
  target_compile_options(morpheus_core INTERFACE -Wall -Wextra -Wpedantic)
endif()

if(MORPHEUS_ENABLE_SANITIZERS)
  if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(morpheus_core INTERFACE -fsanitize=address,undefined -fno-omit-frame-pointer)
    target_link_options(morpheus_core INTERFACE -fsanitize=address,undefined -fno-omit-frame-pointer)
  else()
    message(WARNING "MORPHEUS_ENABLE_SANITIZERS requested, but this compiler is not configured for the sanitizer profile")
  endif()
endif()

enable_testing()

add_executable(morpheus_core_tests tests/test_structures.cpp)
target_link_libraries(morpheus_core_tests PRIVATE morpheus_core)
add_test(NAME morpheus_core_tests COMMAND morpheus_core_tests)

add_executable(morpheus_versioned_slot_tests tests/test_versioned_slot.cpp)
target_link_libraries(morpheus_versioned_slot_tests PRIVATE morpheus_core Threads::Threads)
add_test(NAME morpheus_versioned_slot_tests COMMAND morpheus_versioned_slot_tests)

add_executable(morpheus_core_demo src/demo.cpp)
target_link_libraries(morpheus_core_demo PRIVATE morpheus_core)

add_executable(morpheus_calibrate src/calibrate.cpp)
target_link_libraries(morpheus_calibrate PRIVATE morpheus_core)
add_test(
  NAME morpheus_calibration_smoke
  COMMAND morpheus_calibrate --n 2000 --ops 5000 --seed 1337 --repetitions 3 --warmup 0
)

add_executable(morpheus_baseline_bench src/baseline_bench.cpp)
target_link_libraries(morpheus_baseline_bench PRIVATE morpheus_core)
add_test(
  NAME morpheus_baseline_bench_smoke
  COMMAND morpheus_baseline_bench --n 1000 --ops 2000 --seed 1337 --repetitions 2 --warmup 0
)
