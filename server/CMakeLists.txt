cmake_minimum_required(VERSION 3.10)
project(wisielec_server)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
add_compile_options(-Wall -Wextra)

add_executable(server main.cpp server.cpp)