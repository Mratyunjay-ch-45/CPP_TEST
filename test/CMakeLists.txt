cmake_minimum_required(VERSION 3.14)
project(UnitTests)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find required packages (GMock is included with GTest)
find_package(GTest REQUIRED)

# Add test executable - temporarily using simple test
add_executable(unit_tests
    "simple_test.cpp"
)

# Uncomment these when source files are available:
# add_executable(unit_tests
#     "authcontroller_test.cpp"
#     "departmentscontroller_test.cpp"
#     "jobscontroller_test.cpp"
# )

# Link libraries (modern CMake targets)
target_link_libraries(unit_tests
    GTest::gtest
    GTest::gtest_main
    GTest::gmock
    GTest::gmock_main
)

# Enable testing
enable_testing()
add_test(NAME unit_tests COMMAND unit_tests)

# For coverage (optional)
if(CMAKE_BUILD_TYPE STREQUAL "Debug")
    target_compile_options(unit_tests PRIVATE --coverage)
    target_link_options(unit_tests PRIVATE --coverage)
endif()