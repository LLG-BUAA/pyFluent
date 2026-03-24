# UDF Builder（外部 CMake 编译 Fluent UDF）

本目录提供一个可独立使用的 UDF 编译工具：
**不依赖 Fluent GUI 内置编译器**，在外部用 CMake + VS 工具链生成 `libudf`，再供 Fluent 加载。

---

## 适用场景

- 需要把 UDF 编译流程脚本化、自动化
- 希望脱离 Fluent GUI 做可重复构建
- 需要统一管理多个 `.c/.h/.hpp` 文件并自动更新 `src/CMakeLists.txt`
- 需要批量或远程触发 UDF 编译（HTTP / Python）

---

## 目录说明

- `udf_builder_gradio_preset.py`：核心程序
  - Gradio 可视化界面
  - 对外 Python API：`run_all_from_external(...)`
  - HTTP API：`http_run_all`
- `udf_builder_line.py`：Python 直接调用示例
- `udf_builder_web.py`：HTTP 调用示例
- `CMake_Project_for_UDF/`：UDF CMake 工程模板（含 `CMakePresets.json`）

---

## 环境要求

- Windows
- Python 3.10+
- Visual Studio C/C++ 工具链（`VsDevCmd.bat` 可用）
- CMake（建议 3.21+，支持 Preset）
- Ninja（如果 preset 使用 Ninja）

Python 依赖：

```bash
pip install gradio requests
```

> 如果你在 `pyfluent_ui.py` 中联动使用，还需要 `ansys-fluent-core` 与 `streamlit`。

---

## 编译流程（核心逻辑）

工具的一键流程是：

1. 校验并收集输入 `.c/.h/.hpp`
2. 可选清理 `src/` 中旧源码（保留必要模板文件）
3. 复制源文件到 `CMake_Project_for_UDF/src/`
4. 自动更新 `src/CMakeLists.txt` 的 `CSOURCES/CHEADERS`
5. 执行 `cmake --preset <configure_preset>`
6. 自动修补 `udf_names.c` 中 `extern DEFINE_*` 缺 `;` 问题
7. 执行 `cmake --build --preset <build_preset>`
8. 产出 `libudf`（默认在 `<project_root>/libudf`）

---

## 快速开始

### 1) 启动 Web UI

```bash
python udf_builder_gradio_preset.py
```

默认打开浏览器后，可在界面中使用“仅处理文件 / 仅配置 / 仅补丁 / 仅构建 / 一键执行”。

### 2) 最小 Python 调用示例

```python
from udf_builder_gradio_preset import run_all_from_external

result = run_all_from_external(
    c_file_paths=[r"F:\pyFluent\testUDF.c"],
    h_file_paths=[],
    overrides={
        "project_root": r"F:\pyFluent\udf-builder\CMake_Project_for_UDF"
    },
)

print("ok:", result["ok"])
print("status:", result["status_html"])
print("log:\n", result["log"])
```

### 3) HTTP 调用

先启动 `udf_builder_gradio_preset.py`，默认服务例如 `http://127.0.0.1:7860`。

接口：

- `POST /gradio_api/call/http_run_all`

入参按顺序传 3 个字符串：

1. `c_files_input`
2. `h_files_input`
3. `overrides_input`

格式支持：

- `c_files_input/h_files_input`：JSON 数组字符串或换行分隔路径
- `overrides_input`：JSON 对象字符串

可参考：`udf_builder_web.py`

---

## `overrides` 参数

`run_all_from_external(..., overrides=...)` 目前支持：

- `project_root`：CMake 工程根目录
- `vsdevcmd`：`VsDevCmd.bat` 路径
- `cmake_path`：`cmake.exe` 路径
- `arch`：如 `x64`
- `configure_preset`
- `build_preset`
- `fresh`：configure 时是否 `--fresh`
- `cleanup_before_copy`：复制前清理旧源码
- `sync_headers`：是否写入 `CHEADERS`
- `patch_after_configure`：配置后补丁
- `patch_before_build`：构建前补丁

---

## 结果与产物

`run_all_from_external` 返回字典，常用字段：

- `ok`：是否成功
- `status_html`：状态摘要
- `log`：完整日志
- `errors_html`：提取错误摘要
- `cmake_preview`：写入 `CMakeLists` 的预览
- `command_preview`：执行命令预览

最终编译结果通常在：

- `<project_root>/libudf`

---

## 与 Fluent 集成建议

典型集成方式：

1. 用本工具完成外部构建
2. 将 `libudf` 复制到 case/workspace 目标目录
3. 在 Fluent 中执行：先 `unload`，再 `load`

本仓库的 `pyfluent_ui.py` 已内置这一联动流程（编译 → 部署 → 加载）。

---

## 常见问题排查

### 1) `project_root` 校验失败

确认目录下同时存在：

- 顶层 `CMakeLists.txt`
- `src/CMakeLists.txt`
-（推荐）`CMakePresets.json`

### 2) `preset` 找不到

检查 `CMakePresets.json` 中 `configurePresets/buildPresets` 名称与输入一致。

### 3) 命令执行失败（VS/CMake 路径问题）

重点检查：

- `vsdevcmd` 是否真实存在
- `cmake_path` 是否真实存在
- `arch` 是否与工具链匹配（通常 `x64`）

### 4) 构建报 `udf_names.c` 相关语法错误

开启补丁选项（`patch_after_configure` 或 `patch_before_build`），查看日志中 `[补丁]` 段落是否生效。

### 5) 文件名冲突

如果上传文件存在重名（同 basename），复制到 `src/` 会冲突，需先重命名。

---

## 推荐实践

- 固定一套 `CMakePresets.json` 与编译器版本，减少环境漂移
- 先跑最小单文件 UDF，再逐步扩大源码集合
- 在 CI/自动化环境中优先调用 Python API 或 HTTP API
- 保留 `log` 作为构建审计与故障复盘依据
