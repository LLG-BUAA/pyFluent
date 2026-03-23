from __future__ import annotations

import importlib.util
import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import traceback
from collections import deque
from datetime import datetime
from html import unescape
from pathlib import Path
from typing import Any

import ansys.fluent.core as pyfluent
import streamlit as st
from ansys.fluent.core.launcher.launch_options import (
    Dimension,
    FluentMode,
    Precision,
    UIMode,
)

ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_WORKSPACE = str((ROOT_DIR / "workspace").resolve())
DEFAULT_OUTPUT_DIR = str((ROOT_DIR / "output").resolve())
DEFAULT_UDF_PROJECT_ROOT = str((ROOT_DIR / "udf-builder" / "CMake_Project_for_UDF").resolve())
UDF_BUILDER_FILE = ROOT_DIR / "udf-builder" / "udf_builder_gradio_preset.py"
PROJECT_SUBDIRS = ("Case", "Data", "UDF", "Output", "Animation")
CONSOLE_FAB_RIGHT_PX = 20
CONSOLE_FAB_BOTTOM_PX = 20
CONSOLE_PANEL_MAX_WIDTH_VW = 90
CONSOLE_PANEL_MAX_WIDTH_PX = 3200
CONSOLE_DIALOG_MAX_WIDTH_VW = 90
CONSOLE_DIALOG_MAX_WIDTH_PX = 4096


EXTENSION_HOOKS: dict[str, list] = {
    "before_launch": [],
    "after_launch": [],
    "before_connect": [],
    "after_connect": [],
    "before_action": [],
    "after_action": [],
}


@st.cache_resource
def _runtime_store() -> dict[str, Any]:
    return {"sessions": {}}


def _sessions() -> dict[str, dict[str, Any]]:
    store = _runtime_store()
    sessions = store.get("sessions")
    if not isinstance(sessions, dict):
        sessions = {}
        store["sessions"] = sessions
    return sessions


def _sync_selected_id_to_query() -> None:
    sid = str(st.session_state.get("selected_id", "") or "").strip()
    try:
        if sid:
            st.query_params["sid"] = sid
        elif "sid" in st.query_params:
            del st.query_params["sid"]
    except Exception:
        pass


def _restore_selected_id_from_query() -> None:
    try:
        sid = str(st.query_params.get("sid", "") or "").strip()
    except Exception:
        sid = ""
    if sid and sid in _sessions():
        st.session_state.selected_id = sid


@st.cache_resource
def _console_capture_store() -> dict[str, Any]:
    return {
        "lines": deque(maxlen=6000),
        "lock": threading.Lock(),
        "installed": False,
        "log_handler_installed": False,
        "partial_stdout": "",
        "partial_stderr": "",
    }


class _ConsoleTee:
    def __init__(self, channel: str, original, store: dict[str, Any]):
        self.channel = channel
        self.original = original
        self.store = store

    def write(self, data) -> int:
        text = data.decode("utf-8", errors="replace") if isinstance(data, bytes) else str(data)
        if not text:
            return 0
        _append_console_text(self.channel, text, self.store)
        try:
            return int(self.original.write(text))
        except Exception:
            return len(text)

    def flush(self) -> None:
        _flush_console_partial(self.channel, self.store)
        try:
            self.original.flush()
        except Exception:
            pass

    @property
    def encoding(self):
        return getattr(self.original, "encoding", "utf-8")

    def isatty(self) -> bool:
        return bool(getattr(self.original, "isatty", lambda: False)())

    def __getattr__(self, name):
        return getattr(self.original, name)


class _ConsoleLogHandler(logging.Handler):
    def __init__(self, store: dict[str, Any]):
        super().__init__(level=logging.INFO)
        self.store = store

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
        except Exception:
            message = record.getMessage()
        if message:
            _append_console_text("log", f"{message}\n", self.store)


def _append_console_text(channel: str, text: str, store: dict[str, Any]) -> None:
    lock = store["lock"]
    partial_key = f"partial_{channel}"
    with lock:
        merged = f"{store.get(partial_key, '')}{text}"
        parts = merged.splitlines(keepends=True)
        trailing = ""
        if parts and not parts[-1].endswith(("\n", "\r")):
            trailing = parts.pop()
        timestamp = datetime.now().strftime("%H:%M:%S")
        for part in parts:
            line = part.rstrip("\r\n")
            store["lines"].append(f"{timestamp} [{channel}] {line}")
        store[partial_key] = trailing


def _flush_console_partial(channel: str, store: dict[str, Any]) -> None:
    lock = store["lock"]
    partial_key = f"partial_{channel}"
    with lock:
        pending = str(store.get(partial_key, ""))
        if pending:
            timestamp = datetime.now().strftime("%H:%M:%S")
            store["lines"].append(f"{timestamp} [{channel}] {pending}")
            store[partial_key] = ""


def _install_console_capture() -> None:
    store = _console_capture_store()
    if store.get("installed"):
        return
    sys.stdout = _ConsoleTee("stdout", sys.stdout, store)
    sys.stderr = _ConsoleTee("stderr", sys.stderr, store)
    try:
        sys.__stdout__ = sys.stdout
        sys.__stderr__ = sys.stderr
    except Exception:
        pass

    if not store.get("log_handler_installed"):
        log_handler = _ConsoleLogHandler(store)
        log_handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s: %(message)s"))
        root_logger = logging.getLogger()
        root_logger.addHandler(log_handler)
        root_logger.setLevel(min(root_logger.level, logging.INFO) if root_logger.level else logging.INFO)
        store["log_handler_installed"] = True
    store["installed"] = True


def _clear_console_capture() -> None:
    store = _console_capture_store()
    with store["lock"]:
        store["lines"].clear()
        store["partial_stdout"] = ""
        store["partial_stderr"] = ""


def _console_dump(last_n: int) -> str:
    store = _console_capture_store()
    _flush_console_partial("stdout", store)
    _flush_console_partial("stderr", store)
    with store["lock"]:
        lines = list(store["lines"])
    return "\n".join(lines[-max(1, int(last_n)):])


def register_extension_hook(hook_name: str, handler) -> None:
    if hook_name not in EXTENSION_HOOKS:
        EXTENSION_HOOKS[hook_name] = []
    EXTENSION_HOOKS[hook_name].append(handler)


def run_extension_hooks(hook_name: str, payload: dict[str, Any]) -> None:
    for handler in EXTENSION_HOOKS.get(hook_name, []):
        handler(payload)


def _ok(message: str) -> str:
    return f"✅ {message}"


def _err(error: Exception) -> str:
    return f"❌ {type(error).__name__}: {error}"


def _init_state() -> None:
    defaults = {
        "selected_id": "",
        "status_msg": "就绪",
        "io_msg": "",
        "udf_msg": "",
        "udf_log": "",
        "file_paths_bound_sid": "",
        "case_manual_selected": "",
        "data_manual_selected": "",
        "launch_existing_project": "(新建项目目录)",
        "launch_project_name": "Project_001",
        "launch_workspace_last": "",
        "file_case_name": "model.cas.h5",
        "file_data_name": "model.dat.h5",
        "udf_folder_bound_sid": "",
        "udf_selected_source_rel": "(UDF 根目录)",
        "udf_new_folder_name": "my_udf",
        "console_dialog_open": False,
        "console_show_lines": 1200,
        "workspace_delete_confirm_open": False,
        "workspace_project_to_delete": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    st.session_state.sessions = _sessions()
    if not st.session_state.selected_id:
        _restore_selected_id_from_query()
    st.session_state.selected_id = _resolve_selected_id(st.session_state.selected_id)
    _sync_selected_id_to_query()


def _session_choices() -> list[str]:
    return list(_sessions().keys())


def _resolve_selected_id(selected_id: str | None = None) -> str:
    candidate = str(selected_id or st.session_state.selected_id or "").strip()
    if candidate and candidate in _sessions():
        return candidate
    choices = _session_choices()
    return choices[0] if choices else ""


def _selected_session() -> tuple[str, Any]:
    sid = _resolve_selected_id()
    if not sid:
        raise RuntimeError("当前无可用 Fluent 实例，请先启动或连接。")
    session = _sessions().get(sid) or {}
    solver = session.get("solver")
    if solver is None:
        raise RuntimeError(f"实例 {sid} 不可用，请重新连接或移除后重建。")
    return sid, solver


def _new_session_id(prefix: str) -> str:
    base = prefix.strip() or "session"
    idx = 1
    while f"{base}-{idx:02d}" in _sessions():
        idx += 1
    return f"{base}-{idx:02d}"


def _session_detail_text() -> str:
    sid = _resolve_selected_id()
    if not sid:
        return "暂无实例。"
    meta = (_sessions().get(sid) or {}).get("meta") or {}
    return (
        f"当前实例: {sid}\n"
        f"类型: {meta.get('source', 'unknown')}\n"
        f"项目名: {meta.get('project_name', '')}\n"
        f"项目根目录: {meta.get('project_root', '')}\n"
        f"IP: {meta.get('ip', '')}\n"
        f"Port: {meta.get('port', '')}\n"
        f"Workspace: {meta.get('workspace', '')}"
    )


def _parse_multiline_paths(raw: str) -> list[str]:
    if not raw:
        return []
    return [line.strip() for line in raw.splitlines() if line.strip()]


def _validate_project_name(project_name: str) -> str:
    name = str(project_name or "").strip()
    if not name:
        raise ValueError("项目名不能为空")
    if name in {".", ".."}:
        raise ValueError("项目名非法，请使用普通名称")
    if any(char in name for char in ("\\", "/", ":", "*", "?", '"', "<", ">", "|")):
        raise ValueError("项目名包含非法字符")
    if Path(name).name != name:
        raise ValueError("项目名不能包含路径")
    return name


def _list_workspace_projects(workspace: str) -> list[str]:
    workspace_path = Path(workspace).expanduser().resolve()
    if not workspace_path.exists() or not workspace_path.is_dir():
        return []
    return sorted(item.name for item in workspace_path.iterdir() if item.is_dir())


def _prepare_new_project_scaffold(workspace_path: Path, project_name: str) -> Path:
    existed_dirs = {item.name.lower() for item in workspace_path.iterdir() if item.is_dir()}
    if project_name.lower() in existed_dirs:
        raise FileExistsError(f"项目名冲突：{project_name}，与工作目录下现有文件夹同名")

    project_root = workspace_path / project_name
    project_root.mkdir(parents=True, exist_ok=False)
    for subdir in PROJECT_SUBDIRS:
        (project_root / subdir).mkdir(parents=True, exist_ok=True)
    return project_root


def _ensure_project_subdirs(project_root: Path) -> None:
    project_root.mkdir(parents=True, exist_ok=True)
    for subdir in PROJECT_SUBDIRS:
        (project_root / subdir).mkdir(parents=True, exist_ok=True)


def _session_project_root(sid: str) -> Path:
    meta = (_sessions().get(sid) or {}).get("meta") or {}
    project_root = str(meta.get("project_root", "") or "").strip()
    if project_root:
        return Path(project_root).expanduser().resolve()

    workspace = str(meta.get("workspace", "") or "").strip()
    if workspace:
        return Path(workspace).expanduser().resolve()
    return ROOT_DIR


def _resolve_session_path(sid: str, user_input: str, default_relative: str) -> Path:
    raw = str(user_input or "").strip()
    candidate = Path(raw).expanduser() if raw else Path(default_relative)
    if candidate.is_absolute():
        return candidate.resolve()
    return (_session_project_root(sid) / candidate).resolve()


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _pick_file_dialog(title: str, filetypes: list[tuple[str, str]]) -> str:
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.update_idletasks()
        root.attributes("-topmost", True)
        root.lift()
        root.focus_force()
        selected = filedialog.askopenfilename(title=title, filetypes=filetypes, parent=root)
        root.update_idletasks()
        root.destroy()
        return str(selected or "")
    except Exception:
        return ""


def _save_file_dialog(title: str, default_name: str, filetypes: list[tuple[str, str]]) -> str:
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.update_idletasks()
        root.attributes("-topmost", True)
        root.lift()
        root.focus_force()
        selected = filedialog.asksaveasfilename(
            title=title,
            initialfile=default_name,
            filetypes=filetypes,
            defaultextension=filetypes[0][1].replace("*", "") if filetypes else "",
            parent=root,
        )
        root.update_idletasks()
        root.destroy()
        return str(selected or "")
    except Exception:
        return ""


def _open_folder_in_os(path: Path) -> None:
    folder = Path(path).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    if sys.platform.startswith("win"):
        os.startfile(str(folder))
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(folder)])
    else:
        subprocess.Popen(["xdg-open", str(folder)])


def _delete_workspace_project(workspace: str, project_name: str) -> Path:
    workspace_path = Path(str(workspace or "").strip() or DEFAULT_WORKSPACE).expanduser().resolve()
    if not workspace_path.exists() or not workspace_path.is_dir():
        raise FileNotFoundError(f"工作目录不存在：{workspace_path}")

    safe_project_name = _validate_project_name(project_name)
    target = (workspace_path / safe_project_name).resolve()
    if not target.exists() or not target.is_dir():
        raise FileNotFoundError(f"项目目录不存在：{target}")

    if target == workspace_path:
        raise ValueError("不允许删除工作目录本身")

    target_norm = str(target).lower()
    using_sessions: list[str] = []
    for sid, info in _sessions().items():
        meta = (info or {}).get("meta") or {}
        project_root = str(meta.get("project_root", "") or "").strip()
        if project_root and str(Path(project_root).expanduser().resolve()).lower() == target_norm:
            using_sessions.append(sid)
    if using_sessions:
        joined = ", ".join(using_sessions)
        raise RuntimeError(f"目录正在被实例使用，无法删除：{joined}")

    shutil.rmtree(target)
    return target


def _render_delete_project_dialog(workspace: str) -> None:
    if not st.session_state.get("workspace_delete_confirm_open", False):
        return

    project_name = str(st.session_state.get("workspace_project_to_delete", "") or "").strip()
    workspace_path = Path(str(workspace or "").strip() or DEFAULT_WORKSPACE).expanduser().resolve()

    if hasattr(st, "dialog"):
        @st.dialog("删除项目目录确认")
        def _dialog_body():
            st.warning(f"将删除目录及其全部内容：\n{workspace_path / project_name}")
            st.caption("该操作不可恢复。")
            c1, c2 = st.columns([1, 1])
            with c1:
                if st.button("确认", key="workspace_delete_confirm_yes", use_container_width=True):
                    try:
                        deleted = _delete_workspace_project(workspace, project_name)
                        st.session_state.status_msg = _ok(f"已删除项目目录：{deleted}")
                        st.session_state.workspace_delete_confirm_open = False
                        st.session_state.workspace_project_to_delete = ""
                        st.session_state.launch_existing_project = "(新建项目目录)"
                        st.session_state.launch_workspace_last = ""
                        st.rerun()
                    except Exception as error:
                        st.session_state.status_msg = _err(error)
                        st.session_state.workspace_delete_confirm_open = False
                        st.session_state.workspace_project_to_delete = ""
                        st.rerun()
            with c2:
                if st.button("取消", key="workspace_delete_confirm_no", use_container_width=True):
                    st.session_state.workspace_delete_confirm_open = False
                    st.session_state.workspace_project_to_delete = ""
                    st.rerun()

        _dialog_body()
        return

    st.warning(f"将删除目录及其全部内容：{workspace_path / project_name}")
    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("确认", key="workspace_delete_confirm_yes_fallback", use_container_width=True):
            try:
                deleted = _delete_workspace_project(workspace, project_name)
                st.session_state.status_msg = _ok(f"已删除项目目录：{deleted}")
                st.session_state.workspace_delete_confirm_open = False
                st.session_state.workspace_project_to_delete = ""
                st.session_state.launch_existing_project = "(新建项目目录)"
                st.session_state.launch_workspace_last = ""
                st.rerun()
            except Exception as error:
                st.session_state.status_msg = _err(error)
                st.session_state.workspace_delete_confirm_open = False
                st.session_state.workspace_project_to_delete = ""
                st.rerun()
    with c2:
        if st.button("取消", key="workspace_delete_confirm_no_fallback", use_container_width=True):
            st.session_state.workspace_delete_confirm_open = False
            st.session_state.workspace_project_to_delete = ""
            st.rerun()


def _list_case_files_for_session(sid: str) -> list[str]:
    root = _session_project_root(sid)
    case_dir = root / "Case"
    patterns = ("*.cas", "*.cas.h5")
    found: list[Path] = []

    if case_dir.exists():
        for pattern in patterns:
            found.extend(case_dir.glob(pattern))

    for pattern in patterns:
        found.extend(root.glob(pattern))

    return sorted({str(p.resolve()) for p in found})


def _list_data_files_for_session(sid: str) -> list[str]:
    root = _session_project_root(sid)
    data_dir = root / "Data"
    patterns = ("*.dat", "*.dat.h5")
    found: list[Path] = []

    if data_dir.exists():
        for pattern in patterns:
            found.extend(data_dir.glob(pattern))

    for pattern in patterns:
        found.extend(root.glob(pattern))

    return sorted({str(p.resolve()) for p in found})


def _session_udf_root(sid: str) -> Path:
    return (_session_project_root(sid) / "UDF").resolve()


def _list_udf_source_folders_for_session(sid: str) -> list[str]:
    udf_root = _session_udf_root(sid)
    udf_root.mkdir(parents=True, exist_ok=True)
    options = ["(UDF 根目录)"]
    subdirs = sorted([item.name for item in udf_root.iterdir() if item.is_dir()])
    options.extend(subdirs)
    return options


def _resolve_udf_source_dir(sid: str, selected_rel: str) -> Path:
    udf_root = _session_udf_root(sid)
    selected_rel = str(selected_rel or "").strip()
    if not selected_rel or selected_rel == "(UDF 根目录)":
        return udf_root
    return (udf_root / selected_rel).resolve()


def _scan_udf_sources(source_dir: Path) -> tuple[list[Path], list[Path]]:
    c_files = sorted(source_dir.rglob("*.c"))
    h_files = sorted([*source_dir.rglob("*.h"), *source_dir.rglob("*.hpp")])
    return c_files, h_files


def _sync_file_defaults_for_selected_session() -> None:
    sid = _resolve_selected_id()
    if st.session_state.file_paths_bound_sid == sid:
        return

    if not sid:
        st.session_state.file_case_name = "model.cas.h5"
        st.session_state.file_data_name = "model.dat.h5"
        st.session_state.case_manual_selected = ""
        st.session_state.data_manual_selected = ""
    else:
        meta = (_sessions().get(sid) or {}).get("meta") or {}
        project_name = str(meta.get("project_name", sid) or sid)

        st.session_state.file_case_name = f"{project_name}.cas.h5"
        st.session_state.file_data_name = f"{project_name}.dat.h5"
        st.session_state.case_manual_selected = ""
        st.session_state.data_manual_selected = ""

    st.session_state.file_paths_bound_sid = sid


def _sync_udf_defaults_for_selected_session() -> None:
    sid = _resolve_selected_id()
    if st.session_state.udf_folder_bound_sid == sid:
        return

    if not sid:
        st.session_state.udf_selected_source_rel = "(UDF 根目录)"
    else:
        options = _list_udf_source_folders_for_session(sid)
        if st.session_state.udf_selected_source_rel not in options:
            st.session_state.udf_selected_source_rel = options[0]

    st.session_state.udf_folder_bound_sid = sid


def _resolve_launch_project(workspace: str, existing_project: str, new_project_name: str) -> tuple[Path, str, str]:
    workspace_path = Path(workspace).expanduser().resolve()
    workspace_path.mkdir(parents=True, exist_ok=True)

    existing_project = str(existing_project or "").strip()
    if existing_project and existing_project != "(新建项目目录)":
        project_root = (workspace_path / existing_project).resolve()
        if not project_root.exists() or not project_root.is_dir():
            raise FileNotFoundError(f"选中的已有项目目录不存在：{project_root}")
        _ensure_project_subdirs(project_root)
        return project_root, existing_project, "existing"

    safe_project_name = _validate_project_name(new_project_name)
    project_root = _prepare_new_project_scaffold(workspace_path, safe_project_name)
    return project_root, safe_project_name, "new"


def launch_session(processor_count: int, workspace: str, existing_project: str, project_name: str) -> None:
    workspace_path = Path(workspace).expanduser().resolve()
    project_root, resolved_project_name, project_mode = _resolve_launch_project(
        workspace=workspace,
        existing_project=existing_project,
        new_project_name=project_name,
    )

    payload = {
        "processor_count": int(processor_count),
        "workspace": str(workspace_path),
        "project_name": resolved_project_name,
        "project_root": str(project_root),
        "project_mode": project_mode,
    }
    run_extension_hooks("before_launch", payload)

    solver = pyfluent.launch_fluent(
        dimension=Dimension.TWO,
        precision=Precision.DOUBLE,
        processor_count=max(1, int(processor_count)),
        ui_mode=UIMode.GUI,
        mode=FluentMode.SOLVER,
        cleanup_on_exit=True,
        py=False,
        cwd=str(project_root),
    )
    conn = solver.connection_properties
    sid = _new_session_id("launch")
    _sessions()[sid] = {
        "solver": solver,
        "meta": {
            "source": "launch",
            "ip": str(conn.ip),
            "port": str(conn.port),
            "password": str(conn.password),
            "workspace": str(workspace_path),
            "project_name": resolved_project_name,
            "project_root": str(project_root),
            "project_mode": project_mode,
        },
    }
    st.session_state.selected_id = sid
    _sync_selected_id_to_query()
    run_extension_hooks("after_launch", {"session_id": sid, "connection": conn})

    if project_mode == "existing":
        st.session_state.status_msg = _ok(f"Fluent 启动成功。当前实例 {sid}，使用已有项目目录：{project_root}")
    else:
        st.session_state.status_msg = _ok(f"Fluent 启动成功。当前实例 {sid}，新建项目={resolved_project_name}，根目录={project_root}")

    st.session_state.file_paths_bound_sid = ""
    st.session_state.udf_folder_bound_sid = ""


def connect_session(ip: str, port: str, password: str) -> None:
    payload = {"ip": str(ip).strip() or "localhost", "port": int(str(port).strip())}
    run_extension_hooks("before_connect", payload)

    solver = pyfluent.connect_to_fluent(
        ip=str(ip).strip() or "localhost",
        port=int(str(port).strip()),
        password=str(password).strip(),
    )
    health = solver.health_check.check_health()
    sid = _new_session_id("conn")
    _sessions()[sid] = {
        "solver": solver,
        "meta": {
            "source": "connect",
            "ip": str(ip).strip() or "localhost",
            "port": str(port).strip(),
            "password": str(password).strip(),
            "workspace": "",
            "project_name": "",
            "project_root": "",
        },
    }
    st.session_state.selected_id = sid
    _sync_selected_id_to_query()
    run_extension_hooks("after_connect", {"session_id": sid, "health": str(health)})
    st.session_state.status_msg = _ok(f"连接成功。当前实例 {sid}，健康检查：{health}")
    st.session_state.file_paths_bound_sid = ""
    st.session_state.udf_folder_bound_sid = ""


def remove_session() -> None:
    sid = _resolve_selected_id()
    if not sid:
        st.session_state.status_msg = "暂无可移除实例。"
        return
    solver = (_sessions().get(sid) or {}).get("solver")
    if solver is not None:
        st.session_state.status_msg = f"实例 {sid} 仍在托管中。请使用“关闭并移除”触发 .exit() 后再移除。"
        return
    _sessions().pop(sid, None)
    st.session_state.selected_id = _resolve_selected_id("")
    _sync_selected_id_to_query()
    st.session_state.status_msg = _ok(f"已移除实例 {sid}")


def close_session() -> None:
    sid = _resolve_selected_id()
    if not sid:
        st.session_state.status_msg = "暂无可关闭实例。"
        return
    solver = (_sessions().get(sid) or {}).get("solver")
    try:
        closer = getattr(solver, "exit", None)
        if callable(closer):
            closer()
    except Exception:
        pass
    _sessions().pop(sid, None)
    st.session_state.selected_id = _resolve_selected_id("")
    _sync_selected_id_to_query()
    st.session_state.status_msg = _ok(f"已关闭并移除实例 {sid}")
    st.session_state.file_paths_bound_sid = ""
    st.session_state.udf_folder_bound_sid = ""


def check_health() -> None:
    sid, solver = _selected_session()
    health = solver.health_check.check_health()
    st.session_state.status_msg = _ok(f"[{sid}] 健康检查通过：{health}")


def _run_session_action(action_name: str, func):
    sid, solver = _selected_session()
    run_extension_hooks("before_action", {"action": action_name, "session_id": sid})
    result = func(sid, solver)
    run_extension_hooks("after_action", {"action": action_name, "session_id": sid})
    return result


def read_case_file(case_file: str) -> None:
    def action(sid: str, solver):
        file_path = _resolve_session_path(sid, case_file, "Case/model.cas.h5")
        if not file_path.exists():
            raise FileNotFoundError(f"未找到 case 文件: {file_path}")
        solver.settings.file.read(file_type="case", file_name=str(file_path))
        return _ok(f"[{sid}] 已读取 case：{file_path}")

    st.session_state.io_msg = _run_session_action("read_case", action)


def read_data_file(data_file: str) -> None:
    def action(sid: str, solver):
        file_path = _resolve_session_path(sid, data_file, "Data/model.dat.h5")
        if not file_path.exists():
            raise FileNotFoundError(f"未找到 data 文件: {file_path}")
        solver.settings.file.read(file_type="data", file_name=str(file_path))
        return _ok(f"[{sid}] 已读取 data：{file_path}")

    st.session_state.io_msg = _run_session_action("read_data", action)


def write_case_file(case_file: str) -> None:
    def action(sid: str, solver):
        target = _resolve_session_path(sid, case_file, "Case/model.cas.h5")
        target.parent.mkdir(parents=True, exist_ok=True)
        solver.settings.file.write_case(file_name=str(target))
        return _ok(f"[{sid}] 已保存 case：{target}")

    st.session_state.io_msg = _run_session_action("write_case", action)
    st.session_state.file_paths_bound_sid = ""
    st.session_state.case_manual_selected = str(_resolve_session_path(_resolve_selected_id(), case_file, "Case/model.cas.h5"))


def write_data_file(data_file: str) -> None:
    def action(sid: str, solver):
        target = _resolve_session_path(sid, data_file, "Data/model.dat.h5")
        target.parent.mkdir(parents=True, exist_ok=True)
        solver.settings.file.write_data(file_name=str(target))
        return _ok(f"[{sid}] 已保存 data：{target}")

    st.session_state.io_msg = _run_session_action("write_data", action)
    st.session_state.file_paths_bound_sid = ""
    st.session_state.data_manual_selected = str(_resolve_session_path(_resolve_selected_id(), data_file, "Data/model.dat.h5"))


def write_case_by_name(file_name: str) -> None:
    name = str(file_name or "").strip()
    if not name:
        raise ValueError("请输入 Case 文件名")

    def action(sid: str, solver):
        target = (_session_project_root(sid) / "Case" / name).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        solver.settings.file.write_case(file_name=str(target))
        return _ok(f"[{sid}] 已保存 case：{target}")

    st.session_state.io_msg = _run_session_action("write_case", action)
    st.session_state.file_paths_bound_sid = ""
    sid = _resolve_selected_id()
    if sid:
        st.session_state.case_manual_selected = str((_session_project_root(sid) / "Case" / name).resolve())


def write_data_by_name(file_name: str) -> None:
    name = str(file_name or "").strip()
    if not name:
        raise ValueError("请输入 Data 文件名")

    def action(sid: str, solver):
        target = (_session_project_root(sid) / "Data" / name).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        solver.settings.file.write_data(file_name=str(target))
        return _ok(f"[{sid}] 已保存 data：{target}")

    st.session_state.io_msg = _run_session_action("write_data", action)
    st.session_state.file_paths_bound_sid = ""
    sid = _resolve_selected_id()
    if sid:
        st.session_state.data_manual_selected = str((_session_project_root(sid) / "Data" / name).resolve())


def _load_udf_builder_module():
    if not UDF_BUILDER_FILE.exists():
        raise FileNotFoundError(f"未找到 UDF Builder：{UDF_BUILDER_FILE}")

    spec = importlib.util.spec_from_file_location("udf_builder_gradio_preset", str(UDF_BUILDER_FILE))
    if spec is None or spec.loader is None:
        raise RuntimeError("加载 udf_builder_gradio_preset 模块失败")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_udf(c_files: list[str], h_files: list[str], project_root: str) -> tuple[str, str, dict[str, Any]]:
    c_paths = [str(Path(p).resolve()) for p in c_files if str(p).strip()]
    h_paths = [str(Path(p).resolve()) for p in h_files if str(p).strip()]
    if not c_paths:
        raise ValueError("当前 UDF 文件夹中未找到 .c 文件")

    module = _load_udf_builder_module()
    if not hasattr(module, "run_all_from_external"):
        raise AttributeError("udf_builder_gradio_preset 中缺少 run_all_from_external")

    overrides = {}
    project_root = str(project_root).strip()
    if project_root:
        overrides["project_root"] = project_root

    payload = module.run_all_from_external(
        c_file_paths=c_paths,
        h_file_paths=h_paths,
        overrides=overrides or None,
    )

    ok = bool(payload.get("ok"))
    status_html = unescape(str(payload.get("status_html", "")))
    log = str(payload.get("log", ""))
    status_text = _ok("UDF 编译完成") if ok else "❌ UDF 编译失败"
    return f"{status_text}\n{status_html}", log, payload


def build_udf_from_folder(source_dir: Path, udf_cmake_project_root: str) -> tuple[str, str, dict[str, Any], list[str], list[str]]:
    c_paths, h_paths = _scan_udf_sources(source_dir)
    summary, log, payload = build_udf(
        c_files=[str(p) for p in c_paths],
        h_files=[str(p) for p in h_paths],
        project_root=udf_cmake_project_root,
    )
    return summary, log, payload, [str(p) for p in c_paths], [str(p) for p in h_paths]


def _compiled_libudf_dir(udf_cmake_project_root: str) -> Path:
    return (Path(udf_cmake_project_root).expanduser().resolve() / "libudf").resolve()


def _deploy_compiled_udf_to_target(udf_cmake_project_root: str, target_dir: Path) -> Path:
    compiled_dir = _compiled_libudf_dir(udf_cmake_project_root)
    if not compiled_dir.exists() or not compiled_dir.is_dir():
        raise FileNotFoundError(f"未找到已编译 libudf 目录：{compiled_dir}")

    target_dir = Path(target_dir).expanduser().resolve()
    if target_dir.exists():
        shutil.rmtree(target_dir, ignore_errors=True)
    shutil.copytree(compiled_dir, target_dir)
    return target_dir


def deploy_compiled_udf_to_source_folder(udf_cmake_project_root: str, source_dir: Path) -> Path:
    return _deploy_compiled_udf_to_target(udf_cmake_project_root, (source_dir / "libudf").resolve())


def deploy_compiled_udf_for_session(
    udf_cmake_project_root: str,
    source_dir: Path,
    sid: str,
) -> list[Path]:
    deployed: list[Path] = []
    candidates = [
        (Path(source_dir).expanduser().resolve() / "libudf").resolve(),
        (_session_project_root(sid) / "libudf").resolve(),
    ]
    seen: set[str] = set()
    for target in candidates:
        key = str(target).lower()
        if key in seen:
            continue
        seen.add(key)
        deployed.append(_deploy_compiled_udf_to_target(udf_cmake_project_root, target))
    return deployed


def unload_udf_library(library_name: str) -> str:
    udf_name = str(library_name).strip() or "libudf"

    def action(sid: str, solver):
        try:
            solver.settings.setup.user_defined.unload(library_name=udf_name)
            return _ok(f"[{sid}] 已卸载 UDF：{udf_name}")
        except Exception as e:
            return f"⚠️ [{sid}] 卸载 UDF 时忽略异常：{type(e).__name__}: {e}"

    return _run_session_action("unload_udf", action)


def load_udf_library(library_name: str, udf_cmake_project_root: str | None = None, source_dir: Path | None = None) -> None:
    udf_name = str(library_name).strip() or "libudf"

    messages: list[str] = []
    messages.append(unload_udf_library(udf_name))

    def action(sid: str, solver):
        if udf_cmake_project_root and source_dir:
            deployed_paths = deploy_compiled_udf_for_session(udf_cmake_project_root, source_dir, sid)
            deployed_text = "\n".join(str(p) for p in deployed_paths)
            messages.append(_ok(f"[{sid}] 已部署编译结果到：\n{deployed_text}"))
        solver.settings.setup.user_defined.load(library_name=udf_name)
        return _ok(f"[{sid}] UDF 加载成功：{udf_name}")

    messages.append(_run_session_action("load_udf", action))
    st.session_state.udf_msg = "\n".join(messages)


def build_and_load_udf_from_folder(source_dir: Path, udf_cmake_project_root: str, library_name: str) -> None:
    summary, log, payload, c_paths, h_paths = build_udf_from_folder(source_dir, udf_cmake_project_root)
    st.session_state.udf_log = (
        f"源目录：{source_dir}\n"
        f"C 文件数量：{len(c_paths)}\n"
        f"H 文件数量：{len(h_paths)}\n"
        f"{'-' * 60}\n{log}"
    )
    st.session_state.udf_msg = summary
    if payload.get("ok"):
        load_udf_library(
            library_name=library_name,
            udf_cmake_project_root=udf_cmake_project_root,
            source_dir=source_dir,
        )


def save_uploaded_udf_files_to_folder(uploaded_files, target_dir: Path) -> list[Path]:
    target_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    for uploaded in uploaded_files or []:
        filename = Path(uploaded.name).name
        suffix = Path(filename).suffix.lower()
        if suffix not in {".c", ".h", ".hpp"}:
            continue
        dest = (target_dir / filename).resolve()
        with open(dest, "wb") as f:
            f.write(uploaded.getbuffer())
        saved.append(dest)
    return saved


def create_udf_source_folder(folder_name: str) -> Path:
    sid = _resolve_selected_id()
    if not sid:
        raise RuntimeError("请先启动或连接 Fluent 实例。")
    safe_name = _validate_project_name(folder_name)
    target = (_session_udf_root(sid) / safe_name).resolve()
    target.mkdir(parents=True, exist_ok=True)
    return target


def export_session_manifest() -> str:
    manifest = {"selected_id": st.session_state.selected_id, "sessions": {}}
    for sid, info in _sessions().items():
        manifest["sessions"][sid] = {"meta": (info or {}).get("meta") or {}}
    return json.dumps(manifest, ensure_ascii=False, indent=2)


def _render_console_content(prefix: str = "console") -> None:
    c2, c4 = st.columns([1, 1])
    with c2:
        show_lines = st.number_input(
            "显示最近行数",
            min_value=100,
            max_value=6000,
            value=int(st.session_state.console_show_lines),
            step=100,
            key=f"{prefix}_show_lines",
        )
        st.session_state.console_show_lines = int(show_lines)
    with c4:
        st.download_button(
            "下载控制台日志",
            data=_console_dump(int(show_lines)),
            file_name=f"pyfluent_console_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
            mime="text/plain",
            use_container_width=True,
            key=f"{prefix}_download",
        )

        r1, r2 = st.columns([1, 1])
        with r1:
            if st.button("清空控制台", key=f"{prefix}_clear", use_container_width=True):
                _clear_console_capture()
                st.rerun()
        with r2:
            if st.button("手动刷新", key=f"{prefix}_refresh_now", use_container_width=True):
                st.rerun()

    console_text = _console_dump(int(show_lines))
    st.text_area(
        "Console",
        value=console_text,
        height=600,
        disabled=False,
    )


def _render_console_dialog() -> None:
    if hasattr(st, "dialog"):
        @st.dialog("控制台输出", width="large")
        def _dialog_body():
            _render_console_content(prefix="console_dialog")
            if st.button("关闭", key="console_dialog_close", use_container_width=True):
                st.session_state.console_dialog_open = False
                st.rerun()

        _dialog_body()
        return

    with st.expander("控制台输出", expanded=True):
        _render_console_content(prefix="console_fallback")


def _render_console_fab() -> None:
    store = _console_capture_store()
    with store["lock"]:
        total_lines = len(store["lines"])

    st.markdown(
        f"""
        <style>
        :root {{
          --fab-right: {int(CONSOLE_FAB_RIGHT_PX)}px;
          --fab-bottom: {int(CONSOLE_FAB_BOTTOM_PX)}px;
        }}
        .st-key-console_fab_anchor {{
          position: fixed !important;
          right: var(--fab-right) !important;
          bottom: var(--fab-bottom) !important;
          left: auto !important;
          width: auto !important;
          margin: 0 !important;
          z-index: 9999 !important;
        }}
        .st-key-console_fab_anchor [data-testid="stPopover"],
        .st-key-console_fab_anchor [data-testid="stButton"] {{
          position: fixed !important;
          right: var(--fab-right) !important;
          bottom: var(--fab-bottom) !important;
          left: auto !important;
          width: auto !important;
          margin: 0 !important;
          z-index: 9999 !important;
        }}
        .st-key-console_fab_anchor button {{
          border-radius: 999px !important;
          padding: 0.45rem 1rem !important;
          box-shadow: 0 8px 24px rgba(0, 0, 0, 0.24) !important;
        }}
        div[data-testid="stPopoverContent"] {{
          width: min({int(CONSOLE_PANEL_MAX_WIDTH_VW)}vw, {int(CONSOLE_PANEL_MAX_WIDTH_PX)}px) !important;
          max-width: min({int(CONSOLE_PANEL_MAX_WIDTH_VW)}vw, {int(CONSOLE_PANEL_MAX_WIDTH_PX)}px) !important;
        }}
        div[data-testid="stDialog"] > div {{
          width: min({int(CONSOLE_DIALOG_MAX_WIDTH_VW)}vw, {int(CONSOLE_DIALOG_MAX_WIDTH_PX)}px) !important;
          max-width: min({int(CONSOLE_DIALOG_MAX_WIDTH_VW)}vw, {int(CONSOLE_DIALOG_MAX_WIDTH_PX)}px) !important;
        }}
        div[data-testid="stDialog"] {{
          inset: 0 !important;
          padding: 0 !important;
        }}
        div[data-testid="stDialog"] > div {{
          width: 100vw !important;
          max-width: 100vw !important;
          min-width: 100vw !important;
          height: 80vh !important;
          max-height: 80vh !important;
          margin: 0 !important;
          border-radius: 0 !important;
        }}
        div[data-testid="stDialog"] section[role="dialog"] {{
          height: 80vh !important;
        }}
        div[data-testid="stDialog"] [data-testid="stTextArea"] textarea {{
          height: calc(80vh - 280px) !important;
          min-height: calc(80vh - 280px) !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    with st.container(key="console_fab_anchor"):
        if st.button(f"控制台 ({total_lines})", key="console_fab_button"):
            st.session_state.console_dialog_open = True

    if st.session_state.console_dialog_open:
        _render_console_dialog()


def _render_sidebar() -> None:
    st.sidebar.header("会话管理")

    choices = _session_choices()
    selected = _resolve_selected_id()
    if choices:
        index = choices.index(selected) if selected in choices else 0
        select_label = st.sidebar.selectbox("实例列表", options=choices, index=index)
        st.session_state.selected_id = select_label if select_label else ""
        _sync_selected_id_to_query()
    else:
        st.sidebar.selectbox("实例列表", options=["(暂无实例)"], index=0, disabled=True)
        st.session_state.selected_id = ""
        _sync_selected_id_to_query()

    st.sidebar.code(_session_detail_text(), language="text")

    st.sidebar.subheader("启动新实例")
    launch_cores = st.sidebar.number_input("启动核数", min_value=1, value=16, step=1)
    launch_workspace = st.sidebar.text_input("Fluent 工作目录", value=DEFAULT_WORKSPACE, key="launch_workspace_input")

    ws1, ws2 = st.sidebar.columns([1, 1])
    with ws1:
        if st.button("打开工作目录", key="open_launch_workspace", use_container_width=True):
            try:
                _open_folder_in_os(Path(str(launch_workspace or "").strip() or DEFAULT_WORKSPACE))
                st.session_state.status_msg = _ok(f"已打开工作目录：{Path(str(launch_workspace or '').strip() or DEFAULT_WORKSPACE).expanduser().resolve()}")
            except Exception as error:
                st.session_state.status_msg = _err(error)
    with ws2:
        if st.button("刷新目录列表", key="refresh_workspace_projects", use_container_width=True):
            st.session_state.launch_workspace_last = ""
            st.rerun()

    current_workspace = str(launch_workspace or "").strip()
    if current_workspace != st.session_state.launch_workspace_last:
        workspace_projects = _list_workspace_projects(current_workspace)
        default_existing = "(新建项目目录)"
        if st.session_state.launch_existing_project not in [default_existing, *workspace_projects]:
            st.session_state.launch_existing_project = default_existing
        st.session_state.launch_workspace_last = current_workspace
    else:
        workspace_projects = _list_workspace_projects(current_workspace)

    existing_project_options = ["(新建项目目录)", *workspace_projects]
    st.sidebar.caption(f"当前工作目录下已有文件夹（{len(workspace_projects)}）")
    selected_existing_project = st.sidebar.selectbox(
        "已有项目目录",
        options=existing_project_options,
        key="launch_existing_project",
    )

    ep1, ep2 = st.sidebar.columns([1, 1])
    with ep1:
        if st.button("打开已选目录", key="open_existing_project", use_container_width=True):
            try:
                if selected_existing_project == "(新建项目目录)":
                    st.session_state.status_msg = "请先选择一个已有项目目录。"
                else:
                    target = (Path(str(launch_workspace or "").strip() or DEFAULT_WORKSPACE).expanduser().resolve() / selected_existing_project).resolve()
                    _open_folder_in_os(target)
                    st.session_state.status_msg = _ok(f"已打开项目目录：{target}")
            except Exception as error:
                st.session_state.status_msg = _err(error)
    with ep2:
        if st.button("删除已选目录", key="delete_existing_project", use_container_width=True):
            if selected_existing_project == "(新建项目目录)":
                st.session_state.status_msg = "请先选择一个已有项目目录。"
            else:
                st.session_state.workspace_project_to_delete = selected_existing_project
                st.session_state.workspace_delete_confirm_open = True
                st.rerun()

    launch_project_name = st.sidebar.text_input(
        "新项目名（仅在未选择已有目录时生效）",
        key="launch_project_name",
        disabled=(selected_existing_project != "(新建项目目录)"),
    )

    if selected_existing_project == "(新建项目目录)":
        st.sidebar.caption("将使用上面的项目名创建新目录。")
    else:
        st.sidebar.caption(f"将直接使用已有目录：{selected_existing_project}")

    _render_delete_project_dialog(launch_workspace)

    if st.sidebar.button("启动 Fluent", use_container_width=True):
        try:
            launch_session(
                int(launch_cores),
                launch_workspace,
                selected_existing_project,
                launch_project_name,
            )
            st.rerun()
        except Exception as error:
            st.session_state.status_msg = _err(error)

    st.sidebar.subheader("连接现有实例")
    conn_ip = st.sidebar.text_input("IP", value="localhost")
    conn_port = st.sidebar.text_input("Port", value="")
    conn_pwd = st.sidebar.text_input("Password", value="", type="password")
    if st.sidebar.button("连接现有会话", use_container_width=True):
        try:
            connect_session(conn_ip, conn_port, conn_pwd)
            st.rerun()
        except Exception as error:
            st.session_state.status_msg = _err(error)

    col1, col2, col3 = st.sidebar.columns(3)
    if col1.button("健康检查", use_container_width=True):
        try:
            check_health()
        except Exception as error:
            st.session_state.status_msg = _err(error)
    if col2.button("移除", use_container_width=True):
        remove_session()
        st.rerun()
    if col3.button("关闭并移除", use_container_width=True):
        close_session()
        st.rerun()

    st.sidebar.subheader("实例清单")
    st.sidebar.download_button(
        "下载 JSON",
        data=export_session_manifest(),
        file_name="pyfluent_sessions.json",
        mime="application/json",
        use_container_width=True,
    )


def _render_main() -> None:
    st.title("PyFluent 工作台")
    st.caption("会话管理在左侧边栏；主区用于文件操作与 UDF 操作。")
    st.info(st.session_state.status_msg)

    file_tab, udf_tab = st.tabs(["文件操作", "UDF 操作"])

    with file_tab:
        _sync_file_defaults_for_selected_session()
        st.subheader("读写 Case/Data")
        sid = _resolve_selected_id()

        case_files = _list_case_files_for_session(sid) if sid else []
        data_files = _list_data_files_for_session(sid) if sid else []

        current_case_selected = st.session_state.case_manual_selected or (case_files[0] if case_files else "")
        current_data_selected = st.session_state.data_manual_selected or (data_files[0] if data_files else "")

        case_options = case_files.copy()
        data_options = data_files.copy()

        if current_case_selected and current_case_selected not in case_options:
            case_options = [current_case_selected, *case_options]
        if current_data_selected and current_data_selected not in data_options:
            data_options = [current_data_selected, *data_options]

        if not case_options:
            case_options = ["(当前无 Case 文件)"]
        if not data_options:
            data_options = ["(当前无 Data 文件)"]

        wcd1, wcd2 = st.columns([1, 1])

        with wcd1:
            st.markdown("**读取 Case**")
            case_read_selected = st.selectbox(
                "Case 文件列表",
                options=case_options,
                index=case_options.index(current_case_selected) if current_case_selected in case_options else 0,
                key="case_selectbox_value",
            )

            rb1, rb2 = st.columns([1, 1])
            with rb1:
                if st.button("读取 Case", use_container_width=True):
                    try:
                        if case_read_selected and not str(case_read_selected).startswith("("):
                            st.session_state.case_manual_selected = case_read_selected
                            read_case_file(case_read_selected)
                        else:
                            st.session_state.io_msg = "❌ 当前没有可读取的 Case 文件"
                    except Exception as error:
                        st.session_state.io_msg = _err(error)

            with rb2:
                if st.button("打开其他 Case", use_container_width=True):
                    picked = _pick_file_dialog(
                        "选择 Case 文件",
                        [("Case Files", "*.cas *.cas.h5"), ("All Files", "*.*")],
                    )
                    if picked:
                        st.session_state.case_manual_selected = picked
                        st.rerun()

        with wcd2:
            st.markdown("**读取 Data**")
            data_read_selected = st.selectbox(
                "Data 文件列表",
                options=data_options,
                index=data_options.index(current_data_selected) if current_data_selected in data_options else 0,
                key="data_selectbox_value",
            )

            rb1, rb2 = st.columns([1, 1])
            with rb1:
                if st.button("读取 Data", use_container_width=True):
                    try:
                        if data_read_selected and not str(data_read_selected).startswith("("):
                            st.session_state.data_manual_selected = data_read_selected
                            read_data_file(data_read_selected)
                        else:
                            st.session_state.io_msg = "❌ 当前没有可读取的 Data 文件"
                    except Exception as error:
                        st.session_state.io_msg = _err(error)

            with rb2:
                if st.button("打开其他 Data", use_container_width=True):
                    picked = _pick_file_dialog(
                        "选择 Data 文件",
                        [("Data Files", "*.dat *.dat.h5"), ("All Files", "*.*")],
                    )
                    if picked:
                        st.session_state.data_manual_selected = picked
                        st.rerun()

        wsd1, wsd2 = st.columns([1, 1])

        with wsd1:
            st.markdown("**保存 Case**")
            case_name = st.text_input("Case 文件名", key="file_case_name")
            wc2, wc3 = st.columns([1, 1])

            with wc2:
                if st.button("保存", key="btn_save_case", use_container_width=True):
                    try:
                        write_case_by_name(case_name)
                        st.rerun()
                    except Exception as error:
                        st.session_state.io_msg = _err(error)

            with wc3:
                if st.button("另存为", key="btn_save_case_as", use_container_width=True):
                    default_name = case_name or f"case_{_timestamp()}.cas.h5"
                    picked = _save_file_dialog(
                        "Case 另存为",
                        default_name=default_name,
                        filetypes=[("Case Files", "*.cas.h5"), ("All Files", "*.*")],
                    )
                    if picked:
                        try:
                            write_case_file(picked)
                            st.rerun()
                        except Exception as error:
                            st.session_state.io_msg = _err(error)

        with wsd2:
            st.markdown("**保存 Data**")
            data_name = st.text_input("Data 文件名", key="file_data_name")
            wd2, wd3 = st.columns([1, 1])

            with wd2:
                if st.button("保存", key="btn_save_data", use_container_width=True):
                    try:
                        write_data_by_name(data_name)
                        st.rerun()
                    except Exception as error:
                        st.session_state.io_msg = _err(error)

            with wd3:
                if st.button("另存为", key="btn_save_data_as", use_container_width=True):
                    default_name = data_name or f"data_{_timestamp()}.dat.h5"
                    picked = _save_file_dialog(
                        "Data 另存为",
                        default_name=default_name,
                        filetypes=[("Data Files", "*.dat.h5"), ("All Files", "*.*")],
                    )
                    if picked:
                        try:
                            write_data_file(picked)
                            st.rerun()
                        except Exception as error:
                            st.session_state.io_msg = _err(error)

        st.text_area("文件操作状态", value=st.session_state.io_msg, height=120)

    with udf_tab:
        _sync_udf_defaults_for_selected_session()
        st.subheader("编译与加载 UDF")

        sid = _resolve_selected_id()
        if not sid:
            st.warning("请先启动或连接一个 Fluent 实例，再进行 UDF 操作。")
            st.text_area("UDF 状态", value=st.session_state.udf_msg, height=140)
            st.text_area("UDF 日志", value=st.session_state.udf_log, height=360)
            return

        udf_root = _session_udf_root(sid)
        udf_root.mkdir(parents=True, exist_ok=True)

        p1, p2 = st.columns([1, 1])
        with p1:
            udf_cmake_project_root = st.text_input("UDF CMake Project Root", value=DEFAULT_UDF_PROJECT_ROOT)
        with p2:
            library_name = st.text_input("Fluent 库名", value="libudf")

        folder_options = _list_udf_source_folders_for_session(sid)
        if st.session_state.udf_selected_source_rel not in folder_options:
            st.session_state.udf_selected_source_rel = folder_options[0]

        selected_udf_rel = st.selectbox(
            "选择当前 UDF 文件夹",
            options=folder_options,
            index=folder_options.index(st.session_state.udf_selected_source_rel),
            key="udf_selected_source_rel",
        )

        current_udf_dir = _resolve_udf_source_dir(sid, selected_udf_rel)
        current_udf_dir.mkdir(parents=True, exist_ok=True)

        f1, f2 = st.columns([1, 1])
        with f1:
            st.text_input("当前 UDF 文件夹路径", value=str(current_udf_dir), disabled=True)
        with f2:
            new_folder_name = st.text_input("新建 UDF 子文件夹", key="udf_new_folder_name")
            
        o1, o2, o3 = st.columns([1, 1, 1])
        with o1:
            if st.button("打开当前 UDF 文件夹", use_container_width=True):
                try:
                    _open_folder_in_os(current_udf_dir)
                    st.session_state.udf_msg = _ok(f"已打开文件夹：{current_udf_dir}")
                except Exception as error:
                    st.session_state.udf_msg = _err(error)
        with o2:
            if st.button("刷新 UDF 文件夹列表", use_container_width=True):
                st.session_state.udf_folder_bound_sid = ""
                st.rerun()
        with o3:
            if st.button("创建并切换到该文件夹", use_container_width=True):
                try:
                    created = create_udf_source_folder(new_folder_name)
                    st.session_state.udf_selected_source_rel = created.name
                    st.session_state.udf_folder_bound_sid = ""
                    st.session_state.udf_msg = _ok(f"已创建 UDF 文件夹：{created}")
                    st.rerun()
                except Exception as error:
                    st.session_state.udf_msg = _err(error)


        st.markdown("**拖入或选择 UDF 源文件**")
        uploaded_udf_files = st.file_uploader(
            "拖入 .c / .h / .hpp 文件到这里",
            type=["c", "h", "hpp"],
            accept_multiple_files=True,
            key="udf_file_uploader",
        )

        up1, up2 = st.columns([1, 1])
        with up1:
            if st.button("保存上传文件到当前 UDF 文件夹", use_container_width=True):
                try:
                    saved_files = save_uploaded_udf_files_to_folder(uploaded_udf_files, current_udf_dir)
                    if not saved_files:
                        st.session_state.udf_msg = "❌ 没有可保存的 .c/.h/.hpp 文件"
                    else:
                        file_list = "\n".join(str(p) for p in saved_files)
                        st.session_state.udf_msg = _ok(f"已保存 {len(saved_files)} 个文件到：{current_udf_dir}")
                        st.session_state.udf_log = f"保存文件列表：\n{file_list}"
                        st.rerun()
                except Exception:
                    st.session_state.udf_msg = "❌ 保存上传文件异常"
                    st.session_state.udf_log = traceback.format_exc()

        with up2:
            st.caption("上传后的文件会保存到当前选中的 UDF 文件夹中。")

        c_paths, h_paths = _scan_udf_sources(current_udf_dir)
        st.markdown("**当前文件夹自动解析结果**")
        p1, p2 = st.columns([1, 1])
        with p1:
            st.text_area(
                "C 文件列表",
                value="\n".join(str(p) for p in c_paths) if c_paths else "(无 .c 文件)",
                height=320,
            )
        with p2:
            st.text_area(
                "H / HPP 文件列表",
                value="\n".join(str(p) for p in h_paths) if h_paths else "(无 .h / .hpp 文件)",
                height=320,
            )

        d1, d2, d3, d4 = st.columns(4)

        if d1.button("编译 UDF", use_container_width=True):
            try:
                summary, log, payload, c_used, h_used = build_udf_from_folder(current_udf_dir, udf_cmake_project_root)
                st.session_state.udf_msg = summary
                st.session_state.udf_log = (
                    f"源目录：{current_udf_dir}\n"
                    f"C 文件数量：{len(c_used)}\n"
                    f"H 文件数量：{len(h_used)}\n"
                    f"{'-' * 60}\n{log}"
                )
            except Exception:
                st.session_state.udf_msg = "❌ UDF 编译异常"
                st.session_state.udf_log = traceback.format_exc()

        if d2.button("部署并加载 UDF", use_container_width=True):
            try:
                load_udf_library(
                    library_name=library_name,
                    udf_cmake_project_root=udf_cmake_project_root,
                    source_dir=current_udf_dir,
                )
            except Exception:
                st.session_state.udf_msg = "❌ UDF 部署/加载异常"
                st.session_state.udf_log = traceback.format_exc()

        if d3.button("编译并加载 UDF", use_container_width=True, type="primary"):
            try:
                build_and_load_udf_from_folder(current_udf_dir, udf_cmake_project_root, library_name)
            except Exception:
                st.session_state.udf_msg = "❌ 编译并加载异常"
                st.session_state.udf_log = traceback.format_exc()

        if d4.button("仅卸载 UDF", use_container_width=True):
            try:
                st.session_state.udf_msg = unload_udf_library(library_name)
            except Exception:
                st.session_state.udf_msg = "❌ UDF 卸载异常"
                st.session_state.udf_log = traceback.format_exc()

        st.text_area("UDF 状态", value=st.session_state.udf_msg, height=160)
        st.text_area("UDF 日志", value=st.session_state.udf_log, height=360)

    _render_console_fab()


def main() -> None:
    st.set_page_config(page_title="PyFluent 工作台", layout="wide")
    _install_console_capture()
    _init_state()
    _render_sidebar()
    _render_main()


def _running_in_streamlit_context() -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return get_script_run_ctx() is not None
    except Exception:
        return False


def _launch_with_streamlit_cli() -> int:
    script_path = str(Path(__file__).resolve())
    cmd = [sys.executable, "-m", "streamlit", "run", script_path]
    print("检测到当前为普通 Python 启动，正在切换到 Streamlit 模式...")
    print("执行命令:", " ".join(cmd))
    proc = subprocess.run(cmd)
    return int(proc.returncode)


if __name__ == "__main__":
    if _running_in_streamlit_context():
        main()
    else:
        code = _launch_with_streamlit_cli()
        raise SystemExit(code)
