cmake_minimum_required(VERSION 3.20)
project(morpheus_core LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(morpheus_core INTERFACE)
target_include_directories(morpheus_core INTERFACE ${CMAKE_CURRENT_SOURCE_DIR}/include)

if(MSVC)
  target_compile_options(morpheus_core INTERFACE /W4 /permissive-)
else()
  target_compile_options(morpheus_core INTERFACE -Wall -Wextra -Wpedantic)
endif()

enable_testing()
add_executable(morpheus_core_tests tests/test_structures.cpp)
target_link_libraries(morpheus_core_tests PRIVATE morpheus_core)
add_test(NAME morpheus_core_tests COMMAND morpheus_core_tests)

add_executable(morpheus_core_demo src/demo.cpp)
target_link_libraries(morpheus_core_demo PRIVATE morpheus_core)
