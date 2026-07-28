cmake_minimum_required(VERSION 3.20)

add_library(tpcc_core STATIC
    src/util.cpp
    src/transaction_context.cpp
)

target_include_directories(tpcc_core PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

target_link_libraries(tpcc_core PUBLIC tpcc_util)

target_compile_features(tpcc_core PUBLIC cxx_std_23)

target_compile_options(tpcc_core PRIVATE
    -Wall
    -Wextra
    -Wpedantic
)

if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
    target_compile_options(tpcc_core PRIVATE -fcoroutines)
endif()
