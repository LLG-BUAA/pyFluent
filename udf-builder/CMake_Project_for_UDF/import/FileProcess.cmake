foreach(CFILE ${CSOURCES})
    file(STRINGS ${CFILE} SOURCE_STR)
    foreach(LINE ${SOURCE_STR})
        if(LINE MATCHES "^ *DEFINE_[_A-Z]*\\(.*\\)")
            string(REGEX REPLACE "^ *(DEFINE_[_A-Z]*\\(.*\\))"
                "extern \\1;\n" F_DEF ${LINE})
            list(APPEND FUNCTION_DEFS ${F_DEF})
            string(REGEX REPLACE "^ *DEFINE_([_A-Z]*)\\( *([_a-zA-Z0-9]*).*\\)"
                "{\"\\2\", (void (*)(void))\\2, UDF_TYPE_\\1},\n" F_ARR ${LINE})
            list(APPEND FUNCTION_ARRS ${F_ARR})
        endif()
    endforeach(LINE)
endforeach(CFILE)

message("FUNCTION_DEFS: ${FUNCTION_DEFS}")
message("FUNCTION_ARRS: ${FUNCTION_ARRS}")

string(REPLACE "\n {" "\;\n" FUNCTION_DEFS ${FUNCTION_DEFS})
string(REPLACE "\n {" "\n" FUNCTION_ARRS ${FUNCTION_ARRS})

set(UDFNAMES_CONTENT
    "/* This file generated automatically. */\n"
    "/*          Do not modify.            */\n"
    "#include <math.h>\n"
    "#include \"udf.h\"\n"
    "#include \"prop.h\"\n"
    "#include \"dpm.h\"\n"
    "${FUNCTION_DEFS}"
    "__declspec(dllexport) UDF_Data udf_data[] = {\n"
    "${FUNCTION_ARRS}"
    "}\;\n"
    "__declspec(dllexport) int n_udf_data = sizeof(udf_data)/sizeof(UDF_Data)\;\n"
    "#include \"version.h\"\n"
    "__declspec(dllexport) void UDF_Inquire_Release(int *major, int *minor, int *revision)\n"
    "{\n"
    "\t*major = RampantReleaseMajor\;\n"
    "\t*minor = RampantReleaseMinor\;\n"
    "\t*revision = RampantReleaseRevision\;\n"
    "}"
)

file(WRITE udf_names.c ${UDFNAMES_CONTENT})

execute_process(
    COMMAND ${TOOL_PATH}/resolve.exe -udf ${CSOURCES} -head_file ud_io1.h
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
)