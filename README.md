# pyFluent 工作台（含外部 CMake UDF 编译）

这是一个面向 **ANSYS Fluent + PyFluent** 的本地工具集合，目标是把常见流程集中到一个工程里：

- 启动/连接 Fluent 会话（`pyfluent_ui.py` + `streamlit`）
- 会话文件读写与项目目录管理（Case/Data/UDF/Output/Animation）
- 使用独立 `udf-builder` 工程，在 Fluent 外部通过 CMake 预设编译 UDF
- 将编译好的 `libudf` 回灌到会话目录后自动加载

---

## 目录结构（核心）

- `pyfluent_ui.py`：主入口，Streamlit 工作台
- `run_pyfluent.bat`：Windows 一键启动脚本
- `test-py/`：PyFluent 连接、保存、启动等实验脚本
- `udf-builder/`：UDF 外部编译工具
  - `udf_builder_gradio_preset.py`：主程序（Gradio UI + 对外函数 + HTTP API）
  - `udf_builder_line.py`：命令行/脚本调用示例
  - `udf_builder_web.py`：HTTP 接口调用示例
  - `CMake_Project_for_UDF/`：标准 UDF CMake 工程模板（含 `CMakePresets.json`）

UDF 编译专项文档请见：`udf-builder/README.md`

---

## 环境要求

建议在 Windows 下使用（当前工程也按 Windows 路径与工具链组织）。

- Python 3.10+
- ANSYS Fluent（可被 PyFluent 启动或连接）
- Visual Studio C/C++ 工具链（可用 `VsDevCmd.bat`）
- CMake（支持 Presets，建议 3.21+）
- Ninja（若 preset 使用 Ninja）

Python 依赖（按源码导入汇总）：

```bash
pip install ansys-fluent-core streamlit gradio requests
```

---

## 快速开始

### 1) 启动主工作台

方式 A（推荐）：

```bat
run_pyfluent.bat
```

方式 B：

```bash
python pyfluent_ui.py
```

> `pyfluent_ui.py` 会自动切换到 `streamlit run` 模式并打开页面。

### 2) 启动 UDF Builder（独立 Web UI）

```bash
python udf-builder/udf_builder_gradio_preset.py
```

打开后可在页面中执行：文件处理 → 配置 → 补丁 → 构建，或直接“一键执行”。

---

## `udf-builder` 是什么？（重点）

`udf-builder` 提供了一种 **在 Fluent 外部编译 UDF** 的方法，核心思想是：

1. 将用户提供的 `.c/.h/.hpp` 文件复制到一个可控的 CMake 工程 `src/`
2. 自动重写 `src/CMakeLists.txt` 中的 `CSOURCES/CHEADERS`
3. 调用 VS 开发环境 + CMake Preset 完成 configure/build
4. 自动修补常见 `udf_names.c` 问题（`extern DEFINE_*` 缺 `;`）
5. 产出 `libudf` 目录供 Fluent 加载

这样可以把编译过程从 Fluent GUI 内解耦，便于脚本化、复用与排障。

---

## `udf-builder` 工作流细节

### 输入

- `c_file_paths`：至少 1 个 `.c`
- `h_file_paths`：可选 `.h/.hpp`
- `overrides`：可选参数覆盖，如：
  - `project_root`
  - `vsdevcmd`
  - `cmake_path`
  - `arch`
  - `configure_preset`
  - `build_preset`
  - `fresh`
  - `cleanup_before_copy`
  - `sync_headers`
  - `patch_after_configure`
  - `patch_before_build`

### 执行阶段

- 文件处理（可清理旧源文件、复制新文件、更新 `src/CMakeLists.txt`）
- CMake Configure（`cmake --preset ...`）
- `udf_names.c` 补丁（可在 configure 后或 build 前执行）
- CMake Build（`cmake --build --preset ...`）

### 输出

- 结构化结果：`ok/status_html/log/errors_html/...`
- 编译产物目录：`<project_root>/libudf`

---

## 三种调用方式

### 方式 1：Gradio 页面（人工交互）

```bash
python udf-builder/udf_builder_gradio_preset.py
```

适合手动调试和观察完整日志。

### 方式 2：Python 直接调用（脚本集成）

参考 `udf-builder/udf_builder_line.py`：

```python
from udf_builder_gradio_preset import run_all_from_external

result = run_all_from_external(
    c_file_paths=[r"F:\pyFluent\testUDF.c"],
    overrides={"project_root": r"F:\pyFluent\udf-builder\CMake_Project_for_UDF"}
)
print(result["ok"])
print(result["log"])
```

### 方式 3：HTTP API（服务化调用）

启动 Gradio 后可调用：

- `POST /gradio_api/call/http_run_all`

参数按顺序传 3 个字符串：

1. `c_files_input`（JSON 数组或换行路径）
2. `h_files_input`（JSON 数组或换行路径）
3. `overrides_input`（JSON 对象字符串）

`udf-builder/udf_builder_web.py` 已提供请求示例。

---

## 与 `pyfluent_ui.py` 的联动

主工作台会动态加载 `udf-builder/udf_builder_gradio_preset.py` 中的
`run_all_from_external`，实现：

1. 扫描当前 UDF 源目录并触发外部 CMake 编译
2. 将 `<project_root>/libudf` 复制回会话工作目录
3. 通过 PyFluent 执行 `unload`/`load` 完成 UDF 更新

这意味着你可以在同一套 UI 中完成“编译 + 部署 + 加载”。

---

## 常见问题

### 1) 默认路径不在你的机器上

`udf_builder_gradio_preset.py` 中预设了作者本机路径（如 `DEFAULT_VSDEVCMD`、`DEFAULT_CMAKE`）。
请在页面参数中改为你本机可用路径，或通过 `overrides` 覆盖。

### 2) 找不到 preset

确认 `project_root` 下存在：

- `CMakePresets.json`（或 `CMakeUserPresets.json`）
- 顶层 `CMakeLists.txt`
- `src/CMakeLists.txt`

### 3) 构建失败如何排查

优先查看返回中的：

- `errors_html`（提取的关键 error 行）
- `log`（完整日志）

并确认：编译器环境、CMake preset、源文件是否存在重名冲突。

---

## 开发建议

- 先用 `udf_builder_line.py` 跑通最小样例，再接入主流程
- 将 UDF 代码和 CMake 工程模板解耦，便于版本管理
- 在 CI 或自动化脚本中优先使用 `run_all_from_external` 或 HTTP API

---

## 免责声明

本仓库用于本地工程化与流程自动化示例。具体 UDF 源码正确性、Fluent 版本兼容性、编译器兼容性请按你的项目环境验证。