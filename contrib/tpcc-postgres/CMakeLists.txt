cmake_minimum_required(VERSION 3.20)
project(tpcc-postgres LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

if(NOT CMAKE_CXX_COMPILER_ID MATCHES "Clang")
    message(WARNING "TPC-C is designed for Clang 16+. Current compiler: ${CMAKE_CXX_COMPILER_ID}")
endif()

# --- third-party dependencies (vendored under contrib/third_party) ---

set(FMT_INSTALL OFF CACHE BOOL "" FORCE)
set(FMT_TEST OFF CACHE BOOL "" FORCE)
add_subdirectory(${CMAKE_SOURCE_DIR}/contrib/third_party/fmt ${CMAKE_BINARY_DIR}/third_party/fmt)

set(SPDLOG_FMT_EXTERNAL ON CACHE BOOL "" FORCE)
set(SPDLOG_INSTALL OFF CACHE BOOL "" FORCE)
set(SPDLOG_BUILD_EXAMPLE OFF CACHE BOOL "" FORCE)
add_subdirectory(${CMAKE_SOURCE_DIR}/contrib/third_party/spdlog ${CMAKE_BINARY_DIR}/third_party/spdlog)

set(GFLAGS_BUILD_TESTING OFF CACHE BOOL "" FORCE)
add_subdirectory(${CMAKE_SOURCE_DIR}/contrib/third_party/gflags ${CMAKE_BINARY_DIR}/third_party/gflags)

set(SKIP_BUILD_TEST ON CACHE BOOL "" FORCE)
set(BUILD_DOC OFF CACHE BOOL "" FORCE)
add_subdirectory(${CMAKE_SOURCE_DIR}/contrib/third_party/libpqxx ${CMAKE_BINARY_DIR}/third_party/libpqxx)

if(EXISTS "${CMAKE_SOURCE_DIR}/contrib/third_party/ftxui/CMakeLists.txt")
    set(FTXUI_ENABLE_INSTALL OFF CACHE BOOL "" FORCE)
    set(FTXUI_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
    set(FTXUI_BUILD_DOCS OFF CACHE BOOL "" FORCE)
    set(FTXUI_BUILD_TESTS OFF CACHE BOOL "" FORCE)
    add_subdirectory(${CMAKE_SOURCE_DIR}/contrib/third_party/ftxui ${CMAKE_BINARY_DIR}/third_party/ftxui)
    set(TPCC_HAS_TUI ON)
    message(STATUS "ftxui found: TUI support enabled")
else()
    set(TPCC_HAS_TUI OFF)
    message(STATUS "ftxui not found: TUI support disabled")
endif()

# --- shared libraries ---

add_subdirectory(${CMAKE_SOURCE_DIR}/util/tpcc ${CMAKE_BINARY_DIR}/util/tpcc)
add_subdirectory(${CMAKE_SOURCE_DIR}/library/tpcc ${CMAKE_BINARY_DIR}/library/tpcc)

# --- postgres module ---

set(TPCC_POSTGRES_SOURCES
    src/pg_session.cpp
    src/pg_connection_pool.cpp
    src/common_queries.cpp
    src/transaction_neworder.cpp
    src/transaction_delivery.cpp
    src/transaction_payment.cpp
    src/transaction_orderstatus.cpp
    src/transaction_stocklevel.cpp
    src/transaction_simulation.cpp
    src/init.cpp
    src/import.cpp
    src/clean.cpp
    src/check.cpp
    src/path_checker.cpp
    src/terminal.cpp
    src/runner.cpp
    src/main.cpp
)

if(TPCC_HAS_TUI)
    list(APPEND TPCC_POSTGRES_SOURCES
        src/tui_base.cpp
        src/runner_tui.cpp
        src/import_tui.cpp
        src/scroller.cpp
        src/logs_scroller.cpp
    )
endif()

add_executable(tpcc ${TPCC_POSTGRES_SOURCES})

target_include_directories(tpcc PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

target_link_libraries(tpcc PRIVATE
    tpcc_core
    tpcc_util
    libpqxx::pqxx
    gflags
    spdlog::spdlog
    fmt::fmt
)

if(TPCC_HAS_TUI)
    target_link_libraries(tpcc PRIVATE
        ftxui::screen
        ftxui::dom
        ftxui::component
    )
    target_compile_definitions(tpcc PRIVATE TPCC_HAS_TUI=1)
endif()

target_compile_options(tpcc PRIVATE
    -Wall
    -Wextra
    -Wpedantic
)

if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
    target_compile_options(tpcc PRIVATE -fcoroutines)
endif()

set(TPCC_USE_TCMALLOC "AUTO" CACHE STRING "Link tcmalloc: AUTO, ON, or OFF")
set_property(CACHE TPCC_USE_TCMALLOC PROPERTY STRINGS AUTO ON OFF)

if(NOT TPCC_USE_TCMALLOC STREQUAL "OFF")
    if(TPCC_USE_TCMALLOC STREQUAL "ON")
        find_library(TCMALLOC_LIB NAMES tcmalloc tcmalloc_minimal REQUIRED)
    else()
        find_library(TCMALLOC_LIB NAMES tcmalloc tcmalloc_minimal)
    endif()

    if(TCMALLOC_LIB)
        target_link_libraries(tpcc PRIVATE ${TCMALLOC_LIB})
        target_compile_options(tpcc PRIVATE
            -fno-builtin-malloc
            -fno-builtin-calloc
            -fno-builtin-realloc
            -fno-builtin-free
        )
        message(STATUS "tpcc: linking tcmalloc (${TCMALLOC_LIB})")
    endif()
endif()

# --- unit tests ---

if(EXISTS "${CMAKE_SOURCE_DIR}/contrib/third_party/googletest/CMakeLists.txt")
    set(INSTALL_GTEST OFF CACHE BOOL "" FORCE)
    add_subdirectory(${CMAKE_SOURCE_DIR}/contrib/third_party/googletest ${CMAKE_BINARY_DIR}/third_party/googletest)
    enable_testing()

    add_executable(tpcc_tests
        src/ut/spsc_circular_queue_ut.cpp
        src/ut/histogram_ut.cpp
        src/ut/timer_queue_ut.cpp
        src/ut/task_queue_ut.cpp
        src/ut/log_capture_ut.cpp
    )

    target_include_directories(tpcc_tests PRIVATE
        ${CMAKE_SOURCE_DIR}/util/tpcc/include
        ${CMAKE_SOURCE_DIR}/library/tpcc/include
    )
    target_compile_definitions(tpcc_tests PRIVATE TPCC_NO_SPDLOG)

    target_link_libraries(tpcc_tests PRIVATE
        tpcc_util
        tpcc_core
        GTest::gtest
        GTest::gtest_main
        fmt::fmt
    )

    target_compile_options(tpcc_tests PRIVATE -Wall -Wextra -Wpedantic)

    if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
        target_compile_options(tpcc_tests PRIVATE -fcoroutines)
    endif()

    add_test(NAME tpcc_tests COMMAND tpcc_tests)

    add_executable(tpcc_pg_tests
        src/ut/pg_transaction_ut.cpp
        src/pg_session.cpp
        src/pg_connection_pool.cpp
        src/common_queries.cpp
        src/transaction_neworder.cpp
        src/transaction_delivery.cpp
        src/transaction_payment.cpp
        src/transaction_orderstatus.cpp
        src/transaction_stocklevel.cpp
        src/transaction_simulation.cpp
        src/init.cpp
        src/import.cpp
        src/clean.cpp
        src/check.cpp
        src/path_checker.cpp
    )

    target_include_directories(tpcc_pg_tests PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/include
    )

    target_link_libraries(tpcc_pg_tests PRIVATE
        tpcc_core
        tpcc_util
        GTest::gtest
        GTest::gtest_main
        libpqxx::pqxx
        spdlog::spdlog
        fmt::fmt
    )

    target_compile_options(tpcc_pg_tests PRIVATE -Wall -Wextra -Wpedantic)

    if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
        target_compile_options(tpcc_pg_tests PRIVATE -fcoroutines)
    endif()

    add_test(NAME tpcc_pg_tests COMMAND tpcc_pg_tests)
    set_tests_properties(tpcc_pg_tests PROPERTIES LABELS "pg" TIMEOUT 120)
endif()

if(TARGET tpcc)
    enable_testing()
    add_test(
        NAME smoke_test
        COMMAND ${CMAKE_CURRENT_SOURCE_DIR}/tests/smoke_test.sh
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
    )
    set_tests_properties(smoke_test PROPERTIES
        LABELS "pg"
        TIMEOUT 300
        ENVIRONMENT "TPCC_BIN=$<TARGET_FILE:tpcc>"
    )
endif()
