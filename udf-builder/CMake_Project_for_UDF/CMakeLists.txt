cmake_minimum_required(VERSION 3.21)
project(MakeUDF VERSION 0.1 LANGUAGES C CXX)

# 设置fluent目录
set(FLUENT_ROOT "D:/Workstation/Ansys/ANSYS Inc/v252/fluent") # 更改
set(FLUENT_ARCH win64)
# 设置fluent的版本
set(RELEASE 25.2.0)     # 更改
set(LIB_RELEASE 2520)   # 更改
set(TOOL_PATH ${FLUENT_ROOT}/ntbin/${FLUENT_ARCH})

# 设置case类型
set(DIMENSION 2d)           # 更改 2d 或 3d
set(PRECISE dp)             # 更改 dp 或 空
set(PARALLEL_NODE intel)    # 更改 intel 或 msmpi

# 设置引入cmake模块
list(APPEND CMAKE_MODULE_PATH ${CMAKE_SOURCE_DIR}/import)
include(CompilerConfig)
include(CoolPropConfig)

add_subdirectory(src)