cmake_minimum_required(VERSION 3.20)

add_library(tpcc_util STATIC
    src/histogram.cpp
    src/task_queue.cpp
    src/log_backend.cpp
)

target_include_directories(tpcc_util PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

target_compile_features(tpcc_util PUBLIC cxx_std_23)

target_compile_options(tpcc_util PRIVATE
    -Wall
    -Wextra
    -Wpedantic
)

if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
    target_compile_options(tpcc_util PRIVATE -fcoroutines)
endif()

if(TARGET spdlog::spdlog)
    target_link_libraries(tpcc_util PUBLIC spdlog::spdlog)
endif()

if(TARGET fmt::fmt)
    target_link_libraries(tpcc_util PUBLIC fmt::fmt)
endif()
