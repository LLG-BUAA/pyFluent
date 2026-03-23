set(CSOURCES c32h66_dpm.c enthalpy.c fuel_surface.c kinetics.c mass_flux_calculator.c PE_Arrhenius_WAX_Evapor_Ent.c regression.c sources.c)    # C源文件 # 更改
set(CHEADERS c32h66_dpm.h enthalpy.h fuel_surface.h kinetics.h mass_flux_calculator.h regression.h sources.h)    # C头文件 # 更改
set(USER_OBJECTS)       # obj文件 # 更改
set(THIRD_LIBS)         # 第三方库 # 更改

set(VERSION_HOST ${DIMENSION}${PRECISE}_host)
set(VERSION_NODE ${DIMENSION}${PRECISE}_node)

include(FileProcess)
# 添加编译选项
add_compile_definitions(UDF_EXPORTING UDF_NT WIN64)

# 设置include路径
set(UDF_INCLUDE_DIRS
    ${FLUENT_ROOT}/fluent${RELEASE}/src/main
    ${FLUENT_ROOT}/fluent${RELEASE}/src/addon-wrapper
    ${FLUENT_ROOT}/fluent${RELEASE}/src/io
    ${FLUENT_ROOT}/fluent${RELEASE}/src/species
    ${FLUENT_ROOT}/fluent${RELEASE}/src/pbns
    ${FLUENT_ROOT}/fluent${RELEASE}/src/numerics
    ${FLUENT_ROOT}/fluent${RELEASE}/src/sphysics
    ${FLUENT_ROOT}/fluent${RELEASE}/src/storage
    ${FLUENT_ROOT}/fluent${RELEASE}/src/mphase
    ${FLUENT_ROOT}/fluent${RELEASE}/src/bc
    ${FLUENT_ROOT}/fluent${RELEASE}/src/models
    ${FLUENT_ROOT}/fluent${RELEASE}/src/material
    ${FLUENT_ROOT}/fluent${RELEASE}/src/amg
    ${FLUENT_ROOT}/fluent${RELEASE}/src/util
    ${FLUENT_ROOT}/fluent${RELEASE}/src/mesh
    ${FLUENT_ROOT}/fluent${RELEASE}/src/udf
    ${FLUENT_ROOT}/fluent${RELEASE}/src/ht
    ${FLUENT_ROOT}/fluent${RELEASE}/src/dx
    ${FLUENT_ROOT}/fluent${RELEASE}/src/turbulence
    ${FLUENT_ROOT}/fluent${RELEASE}/src/acoustics
    ${FLUENT_ROOT}/fluent${RELEASE}/src/parallel
    ${FLUENT_ROOT}/fluent${RELEASE}/src/etc
    ${FLUENT_ROOT}/fluent${RELEASE}/src/ue
    ${FLUENT_ROOT}/fluent${RELEASE}/src/dpm
    ${FLUENT_ROOT}/fluent${RELEASE}/src/dbns
    ${FLUENT_ROOT}/fluent${RELEASE}/cortex/src
    ${FLUENT_ROOT}/fluent${RELEASE}/client/src
    ${FLUENT_ROOT}/fluent${RELEASE}/tgrid/src
    ${FLUENT_ROOT}/fluent${RELEASE}/PRIME/tgrid/src
    ${FLUENT_ROOT}/fluent${RELEASE}/multiport/src
    ${FLUENT_ROOT}/fluent${RELEASE}/multiport/mpi_wrapper/src
    ${FLUENT_ROOT}/include
)

set(COMM_HOST net)
set(COMM_NODE mpi)

set(FLUENT_LIB_HOST mport fl${LIB_RELEASE})
set(LIBS_HOST ${FLUENT_ROOT}/fluent${RELEASE}/${FLUENT_ARCH}/${VERSION_HOST}
    ${FLUENT_ROOT}/fluent${RELEASE}/multiport/${FLUENT_ARCH}/${COMM_HOST}/shared
)

if ((NOT ${PARALLEL_NODE} STREQUAL "none") AND (NOT ${PARALLEL_NODE} STREQUAL "net"))
    set(PARALLEL_NODE mpi)
endif()
set(FLUENT_LIB_NODE mport fl_${PARALLEL_NODE}${LIB_RELEASE})
set(LIBS_NODE ${FLUENT_ROOT}/fluent${RELEASE}/${FLUENT_ARCH}/${VERSION_NODE}
    ${FLUENT_ROOT}/fluent${RELEASE}/multiport/${FLUENT_ARCH}/${COMM_NODE}/shared
)

#
# HOST libudf
add_library(udfhost SHARED ${CSOURCES} ${CXXSOURCES} udf_names.c)
target_include_directories(udfhost PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${FLUENT_ROOT}/fluent${RELEASE}/${FLUENT_ARCH}/${VERSION_HOST}
    ${UDF_INCLUDE_DIRS}
)
target_link_directories(udfhost PUBLIC ${LIBS_HOST})
target_link_libraries(udfhost PUBLIC ${FLUENT_LIB_HOST} ${THIRD_LIBS})
if(CMAKE_CXX_COMPILER_ID STREQUAL "MSVC")
    set_target_properties(udfhost PROPERTIES
        ARCHIVE_OUTPUT_DIRECTORY_DEBUG ${CMAKE_SOURCE_DIR}/libudf/${FLUENT_ARCH}/${VERSION_HOST}
        LIBRARY_OUTPUT_DIRECTORY_DEBUG ${CMAKE_SOURCE_DIR}/libudf/${FLUENT_ARCH}/${VERSION_HOST}
        RUNTIME_OUTPUT_DIRECTORY_DEBUG ${CMAKE_SOURCE_DIR}/libudf/${FLUENT_ARCH}/${VERSION_HOST}
        ARCHIVE_OUTPUT_DIRECTORY_RELEASE ${CMAKE_SOURCE_DIR}/libudf/${FLUENT_ARCH}/${VERSION_HOST}
        LIBRARY_OUTPUT_DIRECTORY_RELEASE ${CMAKE_SOURCE_DIR}/libudf/${FLUENT_ARCH}/${VERSION_HOST}
        RUNTIME_OUTPUT_DIRECTORY_RELEASE ${CMAKE_SOURCE_DIR}/libudf/${FLUENT_ARCH}/${VERSION_HOST}
        ARCHIVE_OUTPUT_NAME libudf
        LIBRARY_OUTPUT_NAME libudf
        RUNTIME_OUTPUT_NAME libudf
    )
else()
    set_target_properties(udfhost PROPERTIES
        ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/libudf/${FLUENT_ARCH}/${VERSION_HOST}
        LIBRARY_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/libudf/${FLUENT_ARCH}/${VERSION_HOST}
        RUNTIME_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/libudf/${FLUENT_ARCH}/${VERSION_HOST}
        ARCHIVE_OUTPUT_NAME udf
        LIBRARY_OUTPUT_NAME udf
        RUNTIME_OUTPUT_NAME udf
    )
endif()
# HOST libudf
#

#
# NODE libudf
add_library(udfnode SHARED ${CSOURCES} ${CXXSOURCES} udf_names.c)
target_include_directories(udfnode PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${FLUENT_ROOT}/fluent${RELEASE}/${FLUENT_ARCH}/${VERSION_NODE}
    ${UDF_INCLUDE_DIRS}
)
target_link_directories(udfnode PUBLIC ${LIBS_NODE})
target_link_libraries(udfnode PUBLIC ${FLUENT_LIB_NODE} ${THIRD_LIBS})
if(CMAKE_CXX_COMPILER_ID STREQUAL "MSVC")
    set_target_properties(udfnode PROPERTIES
        ARCHIVE_OUTPUT_DIRECTORY_DEBUG ${CMAKE_SOURCE_DIR}/libudf/${FLUENT_ARCH}/${VERSION_NODE}
        LIBRARY_OUTPUT_DIRECTORY_DEBUG ${CMAKE_SOURCE_DIR}/libudf/${FLUENT_ARCH}/${VERSION_NODE}
        RUNTIME_OUTPUT_DIRECTORY_DEBUG ${CMAKE_SOURCE_DIR}/libudf/${FLUENT_ARCH}/${VERSION_NODE}
        ARCHIVE_OUTPUT_DIRECTORY_RELEASE ${CMAKE_SOURCE_DIR}/libudf/${FLUENT_ARCH}/${VERSION_NODE}
        LIBRARY_OUTPUT_DIRECTORY_RELEASE ${CMAKE_SOURCE_DIR}/libudf/${FLUENT_ARCH}/${VERSION_NODE}
        RUNTIME_OUTPUT_DIRECTORY_RELEASE ${CMAKE_SOURCE_DIR}/libudf/${FLUENT_ARCH}/${VERSION_NODE}
        ARCHIVE_OUTPUT_NAME libudf
        LIBRARY_OUTPUT_NAME libudf
        RUNTIME_OUTPUT_NAME libudf
    )
else()
    set_target_properties(udfnode PROPERTIES
        ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/libudf/${FLUENT_ARCH}/${VERSION_NODE}
        LIBRARY_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/libudf/${FLUENT_ARCH}/${VERSION_NODE}
        RUNTIME_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/libudf/${FLUENT_ARCH}/${VERSION_NODE}
        ARCHIVE_OUTPUT_NAME udf
        LIBRARY_OUTPUT_NAME udf
        RUNTIME_OUTPUT_NAME udf
    )
endif()
# NODE libudf
#