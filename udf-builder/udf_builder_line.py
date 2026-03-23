from udf_builder_gradio_preset import run_all_from_external

result = run_all_from_external(
    c_file_paths=[r"F:\pyFluent\testUDF.c"],
    # h_file_paths=[r"F:\tmp\my_udf.h"],
    overrides={"project_root": r"F:\udf-builder\CMake_Project_for_UDF"}
)
print(result["ok"])
print(result["log"])