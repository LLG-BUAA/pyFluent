from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Iterable

import gradio as gr

# ─────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────

APP_STATE_PATH = Path.home() / ".udf_builder_gradio_preset.json"
DEFAULT_PROJECT_ROOT = r"F:\udf-builder\CMake_Project_for_UDF"
DEFAULT_VSDEVCMD = r"D:\VisualStudio\18\Insider\Common7\Tools\VsDevCmd.bat"
DEFAULT_CMAKE = r"D:\VisualStudio\18\Insider\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"
DEFAULT_CONFIGURE_PRESET = "msvc-ninja-release"
DEFAULT_BUILD_PRESET = "msvc-ninja-release"
PRESERVE_IN_SRC = {"CMakeLists.txt", "udf_names.c", "ud_io1.h"}
SOURCE_SUFFIXES = {".c", ".h", ".hpp"}


EXTERNAL_BRIDGE_LOCK = threading.Lock()
EXTERNAL_BRIDGE_STATE = {
    "source": "idle",
    "status": "未触发",
    "ok": None,
    "updated_at": 0.0,
    "log_tail": "",
}

PROGRESS_STATE = {
    "action": "等待",
    "pct": 0.0,
    "desc": "尚未开始",
    "running": False,
    "updated_at": 0.0,
}

UI_SNAPSHOT = {
    "version": 0,
    "data": None,
    "c_files": [],
    "h_files": [],
}


def _strip_html(raw: str) -> str:
    return re.sub(r"<[^>]+>", "", raw or "").strip()


def _set_bridge_state(*, source: str, status: str, ok: bool | None, log: str) -> None:
    with EXTERNAL_BRIDGE_LOCK:
        EXTERNAL_BRIDGE_STATE["source"] = source
        EXTERNAL_BRIDGE_STATE["status"] = status
        EXTERNAL_BRIDGE_STATE["ok"] = ok
        EXTERNAL_BRIDGE_STATE["updated_at"] = time.time()
        lines = (log or "").splitlines()
        EXTERNAL_BRIDGE_STATE["log_tail"] = "\n".join(lines[-12:])


def _set_progress_state(*, action: str, pct: float, desc: str, running: bool) -> None:
    safe_pct = max(0.0, min(1.0, float(pct or 0.0)))
    with EXTERNAL_BRIDGE_LOCK:
        PROGRESS_STATE["action"] = str(action or "")
        PROGRESS_STATE["pct"] = safe_pct
        PROGRESS_STATE["desc"] = str(desc or "")
        PROGRESS_STATE["running"] = bool(running)
        PROGRESS_STATE["updated_at"] = time.time()


def _set_ui_snapshot(result_tuple, c_files: Iterable[str] | None = None, h_files: Iterable[str] | None = None) -> None:
    data = result_tuple[:10]
    c_list = [str(p) for p in (c_files or []) if str(p).strip()]
    h_list = [str(p) for p in (h_files or []) if str(p).strip()]
    with EXTERNAL_BRIDGE_LOCK:
        UI_SNAPSHOT["version"] += 1
        UI_SNAPSHOT["data"] = data
        UI_SNAPSHOT["c_files"] = c_list
        UI_SNAPSHOT["h_files"] = h_list


def _pull_ui_sync(seen_version: int):
    with EXTERNAL_BRIDGE_LOCK:
        version = int(UI_SNAPSHOT.get("version", 0) or 0)
        data = UI_SNAPSHOT.get("data")
        c_files = list(UI_SNAPSHOT.get("c_files", []) or [])
        h_files = list(UI_SNAPSHOT.get("h_files", []) or [])

    bridge_html = _bridge_state_html()
    if version <= int(seen_version or 0) or not data:
        return (
            gr.update(), gr.update(), gr.update(), gr.update(),
            gr.update(), gr.update(), gr.update(), gr.update(),
            gr.update(), gr.update(), gr.update(), gr.update(),
            bridge_html, int(seen_version or 0),
        )

    return (
        data[0], data[1], data[2], data[3],
        data[4], data[5], data[6], data[7],
        data[8], data[9], c_files, h_files,
        bridge_html, version,
    )


def _bridge_state_html() -> str:
    with EXTERNAL_BRIDGE_LOCK:
        source = EXTERNAL_BRIDGE_STATE["source"]
        status = EXTERNAL_BRIDGE_STATE["status"]
        ok = EXTERNAL_BRIDGE_STATE["ok"]
        updated_at = EXTERNAL_BRIDGE_STATE["updated_at"]
        log_tail = EXTERNAL_BRIDGE_STATE["log_tail"]

    if ok is True:
        tag = "成功"
    elif ok is False:
        tag = "失败"
    else:
        tag = "等待"

    when_text = "尚未执行"
    if updated_at > 0:
        when_text = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(updated_at))

    return f"""
    <div class="panel-shell">
      <div class="panel-title">外部 HTTP / 脚本触发状态</div>
      <div class="soft-note" style="margin-bottom:8px;">
        来源：{_esc(str(source))} ｜ 结果：{_esc(tag)} ｜ 时间：{_esc(when_text)}<br>
        状态：{_esc(str(status))}
      </div>
      <div class="error-list" style="max-height:180px;">
        <div class="error-line">{_esc(log_tail or '暂无日志')}</div>
      </div>
    </div>
    """


# ─────────────────────────────────────────────────────────────
# Persistence
# ─────────────────────────────────────────────────────────────

def load_saved_settings() -> dict:
    if APP_STATE_PATH.exists():
        try:
            return json.loads(APP_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_settings(data: dict) -> None:
    try:
        APP_STATE_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────
# File / encoding helpers
# ─────────────────────────────────────────────────────────────

def normalize_uploaded_files(files) -> list[Path]:
    result: list[Path] = []
    if not files:
        return result
    for f in files:
        path = getattr(f, "name", None) or getattr(f, "path", None) or str(f)
        if path:
            result.append(Path(path))
    return result


def _dedupe_paths(paths: Iterable[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def auto_collect_from_folder_upload(folder_uploads, c_existing, h_existing):
    folder_files = normalize_uploaded_files(folder_uploads)
    merged = _dedupe_paths([
        *normalize_uploaded_files(c_existing),
        *normalize_uploaded_files(h_existing),
        *folder_files,
    ])

    c_files = sorted(
        [str(p) for p in merged if p.suffix.lower() == ".c"],
        key=lambda value: value.lower(),
    )
    h_files = sorted(
        [str(p) for p in merged if p.suffix.lower() in {".h", ".hpp"}],
        key=lambda value: value.lower(),
    )

    if not folder_files:
        msg = "未选择文件夹，保持当前上传列表。"
    else:
        c_preview = ", ".join(Path(p).name for p in c_files[:8])
        h_preview = ", ".join(Path(p).name for p in h_files[:8])
        c_more = f"（另有 {len(c_files) - 8} 个）" if len(c_files) > 8 else ""
        h_more = f"（另有 {len(h_files) - 8} 个）" if len(h_files) > 8 else ""
        msg = (
            f"已从文件夹导入 {len(folder_files)} 个文件，"
            f"自动筛选出 C 文件 {len(c_files)} 个、头文件 {len(h_files)} 个。\n"
            f"C 文件预览: {c_preview or '无'} {c_more}\n"
            f"头文件预览: {h_preview or '无'} {h_more}"
        )

    return (
        gr.update(value=c_files),
        gr.update(value=h_files),
        msg,
    )


def detect_encoding(data: bytes) -> str:
    for enc in ("utf-8", "utf-8-sig", "cp936", "gbk", "mbcs"):
        try:
            data.decode(enc)
            return enc
        except Exception:
            continue
    return sys.getdefaultencoding() or "utf-8"


def decode_output(data: bytes) -> str:
    return data.decode(detect_encoding(data), errors="replace")


def read_text_safely(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    enc = detect_encoding(raw)
    return raw.decode(enc, errors="replace"), enc


def write_text_safely(path: Path, text: str, encoding: str) -> None:
    path.write_text(text, encoding=encoding, newline="")


# ─────────────────────────────────────────────────────────────
# Project / preset helpers
# ─────────────────────────────────────────────────────────────

def validate_project(project_root: str) -> tuple[Path, Path, Path, Path]:
    root = Path(project_root).expanduser().resolve()
    src_dir = root / "src"
    src_cmake = src_dir / "CMakeLists.txt"
    udf_names = src_dir / "udf_names.c"

    if not root.exists():
        raise FileNotFoundError(f"CMakeList目录不存在: {root}")
    if not (root / "CMakeLists.txt").exists():
        raise FileNotFoundError(f"未找到顶层 CMakeLists.txt: {root / 'CMakeLists.txt'}")
    if not src_dir.exists():
        raise FileNotFoundError(f"未找到 src 目录: {src_dir}")
    if not src_cmake.exists():
        raise FileNotFoundError(f"未找到 src/CMakeLists.txt: {src_cmake}")
    return root, src_dir, src_cmake, udf_names


def auto_find_project_root(search_root: str | Path | None = None) -> Path | None:
    base = Path(search_root or Path.cwd()).expanduser().resolve()
    if not base.exists():
        return None

    candidates: list[Path] = []
    seen: set[Path] = set()

    for filename in ("CMakePresets.json", "CMakeUserPresets.json"):
        for preset_file in base.rglob(filename):
            parent = preset_file.parent.resolve()
            if parent in seen:
                continue
            seen.add(parent)
            try:
                validate_project(str(parent))
            except Exception:
                continue
            candidates.append(parent)

    if not candidates:
        return None

    def _sort_key(path: Path):
        try:
            depth = len(path.relative_to(base).parts)
        except Exception:
            depth = len(path.parts)
        return depth, str(path).lower()

    return sorted(candidates, key=_sort_key)[0]


def load_preset_names(project_root: str) -> tuple[list[str], list[str]]:
    root = Path(project_root).expanduser()
    configure_names: list[str] = []
    build_names: list[str] = []

    for filename in ("CMakePresets.json", "CMakeUserPresets.json"):
        path = root / filename
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        for item in data.get("configurePresets", []):
            name = item.get("name")
            if name and name not in configure_names:
                configure_names.append(name)

        for item in data.get("buildPresets", []):
            name = item.get("name")
            if name and name not in build_names:
                build_names.append(name)

    if not build_names:
        build_names = configure_names.copy()

    return configure_names, build_names


def check_duplicate_basenames(c_files: Iterable[Path], h_files: Iterable[Path]) -> None:
    names = [p.name for p in [*c_files, *h_files]]
    dup = sorted({name for name in names if names.count(name) > 1})
    if dup:
        raise ValueError("存在重名文件，复制到 src 后会冲突:\n" + "\n".join(dup))


def cleanup_src(src_dir: Path, log: list[str]) -> None:
    for p in sorted(src_dir.iterdir()):
        if not p.is_file():
            continue
        if p.name in PRESERVE_IN_SRC:
            continue
        if p.suffix.lower() in SOURCE_SUFFIXES:
            p.unlink(missing_ok=True)
            log.append(f"[清理] 删除旧文件: {p}")


def copy_files_to_src(
    src_dir: Path, c_files: list[Path], h_files: list[Path], log: list[str]
) -> None:
    for source in [*c_files, *h_files]:
        target = src_dir / source.name
        shutil.copy2(source, target)
        log.append(f"[复制] {source} -> {target}")


def update_src_cmakelists(
    src_cmake: Path,
    c_files: list[Path],
    h_files: list[Path],
    sync_headers: bool,
    log: list[str],
) -> str:
    content, enc = read_text_safely(src_cmake)

    if content.startswith("\ufeff"):
        content = content.lstrip("\ufeff")
        log.append("[提示] 检测到 BOM，已移除后再更新 CMakeLists.txt")

    csources = " ".join(p.name for p in c_files)
    cheaders = " ".join(p.name for p in h_files)
    new_csources = f"set(CSOURCES {csources})    # C源文件 # 更改"
    new_cheaders = f"set(CHEADERS {cheaders})    # C头文件 # 更改"

    cs_pattern = re.compile(
        r"^[\t \ufeff]*set\s*\(\s*CSOURCES\b[^)]*\)\s*(?:#.*)?$",
        flags=re.MULTILINE,
    )
    ch_pattern = re.compile(
        r"^[\t \ufeff]*set\s*\(\s*CHEADERS\b[^)]*\)\s*(?:#.*)?$",
        flags=re.MULTILINE,
    )

    content, c_count = cs_pattern.subn(new_csources, content, count=1)
    if c_count == 0:
        preview = "\n".join(content.splitlines()[:10])
        raise RuntimeError(
            "src/CMakeLists.txt 中未找到 set(CSOURCES ...) 行。\n文件前10行:\n" + preview
        )

    if sync_headers:
        content, h_count = ch_pattern.subn(new_cheaders, content, count=1)
        if h_count == 0:
            preview = "\n".join(content.splitlines()[:10])
            raise RuntimeError(
                "src/CMakeLists.txt 中未找到 set(CHEADERS ...) 行。\n文件前10行:\n" + preview
            )

    write_text_safely(src_cmake, content, enc)
    log.append(f"[更新] {src_cmake}")
    return new_csources + "\n" + new_cheaders


# ─────────────────────────────────────────────────────────────
# Patch udf_names.c
# ─────────────────────────────────────────────────────────────

def patch_udf_names(udf_names: Path) -> tuple[int, str]:
    if not udf_names.exists():
        return 0, f"未找到文件: {udf_names}"

    text, enc = read_text_safely(udf_names)
    lines = text.splitlines(keepends=True)
    patched: list[str] = []
    changed: list[tuple[int, str, str]] = []

    for idx, line in enumerate(lines, start=1):
        base = line.rstrip("\r\n")
        line_ending = line[len(base):]
        stripped = base.strip()

        if stripped.startswith("extern DEFINE_") and not stripped.endswith(";"):
            new_base = base.rstrip() + ";"
            patched.append(new_base + line_ending)
            changed.append((idx, base, new_base))
        else:
            patched.append(line)

    if changed:
        write_text_safely(udf_names, "".join(patched), enc)

    report = [f"补丁目标: {udf_names}"]
    if not changed:
        report.append("未发现需要补 ';' 的 extern DEFINE_* 行。")
    else:
        report.append(f"已修复 {len(changed)} 处。")
        for line_no, old, new in changed[:20]:
            report.append(f"L{line_no}: {old}")
            report.append(f"   -> {new}")
        if len(changed) > 20:
            report.append(f"... 其余 {len(changed) - 20} 处已省略")

    return len(changed), "\n".join(report)


# ─────────────────────────────────────────────────────────────
# Command helpers
# ─────────────────────────────────────────────────────────────

def normalize_cmd_path(path: str) -> str:
    value = str(path or "").strip()
    for _ in range(4):
        nv = value.replace('\\"', '"').replace("\\'", "'").strip()
        if len(nv) >= 2 and nv[0] == nv[-1] and nv[0] in {'"', "'"}:
            nv = nv[1:-1].strip()
        if nv == value:
            break
        value = nv
    return value


def quote_for_cmd(path: str) -> str:
    return '"' + normalize_cmd_path(path).replace('"', '""') + '"'


def make_configure_chain(
    vsdevcmd: str, cmake_path: str, arch: str, configure_preset: str, fresh: bool
) -> str:
    chain = (
        f'call {quote_for_cmd(vsdevcmd)} -arch={arch} '
        f'&& {quote_for_cmd(cmake_path)} --preset {configure_preset}'
    )
    if fresh:
        chain += " --fresh"
    return chain


def make_build_chain(
    vsdevcmd: str, cmake_path: str, arch: str, build_preset: str
) -> str:
    return (
        f'call {quote_for_cmd(vsdevcmd)} -arch={arch} '
        f'&& {quote_for_cmd(cmake_path)} --build --preset {build_preset}'
    )


def build_command_preview(
    vsdevcmd: str,
    cmake_path: str,
    arch: str,
    configure_preset: str,
    build_preset: str,
    fresh: bool,
) -> str:
    cfg = make_configure_chain(vsdevcmd, cmake_path, arch, configure_preset, fresh)
    bld = make_build_chain(vsdevcmd, cmake_path, arch, build_preset)
    return (
        "# 配置命令\n"
        f"cmd.exe /d /c {cfg}\n\n"
        "# 构建命令\n"
        f"cmd.exe /d /c {bld}\n\n"
        "# 执行顺序\n"
        "处理文件 → 配置 → 补丁 udf_names.c → 构建"
    )


def run_process(command: list[str], cwd: Path) -> tuple[int, str]:
    proc = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=False,
    )
    out, _ = proc.communicate()
    return proc.returncode, decode_output(out or b"")


def run_cmd_chain(chain: str, cwd: Path) -> tuple[int, str]:
    script = cwd / f".udf_cmd_chain_{int(time.time() * 1000)}.cmd"
    script.write_text("@echo off\r\n" + chain + "\r\n", encoding="utf-8", newline="")
    try:
        return run_process(["cmd.exe", "/d", "/c", str(script)], cwd=cwd)
    finally:
        script.unlink(missing_ok=True)


# ─────────────────────────────────────────────────────────────
# Diagnostics / settings
# ─────────────────────────────────────────────────────────────

def extract_errors(log: str) -> str:
    matches = []
    for line in log.splitlines():
        low = line.lower()
        if (
            " error " in low
            or low.startswith("error ")
            or "cmake error" in low
            or "failed:" in low
            or "ninja: build stopped" in low
        ):
            matches.append(line)
    return "\n".join(matches[:80]) if matches else "未提取到明显的 error / failed 行。"


def make_diagnostics(log: str, patch_report: str, project_root: str) -> str:
    points: list[str] = []

    if "Configuring incomplete, errors occurred" in log or "配置失败" in log:
        points.append("配置阶段失败；优先查看第一条 CMake Error 或编译器探测失败信息。")
    if "[配置] 完成" in log:
        points.append("配置阶段已成功完成。")
    if "[补丁] 已修复" in log:
        points.append("udf_names.c 缺失分号问题已自动补丁。")
    if "error C2085" in log and "udf_data" in log:
        points.append("日志里仍有 udf_names.c 语法错误；补丁未完全覆盖或存在其他语法问题。")
    if "[构建] 完成" in log:
        points.append("构建阶段已成功完成。")

    libudf = Path(project_root).expanduser() / "libudf"
    if libudf.exists():
        points.append(f"检测到 libudf 目录: {libudf}")

    if patch_report and "已修复" in patch_report:
        points.append("补丁报告显示至少有一处 extern DEFINE_* 已补上 ';'。")

    if not points:
        points.append("未发现明显的阶段结论，请查看完整日志和错误摘要。")

    return "\n".join(f"- {p}" for p in points)


def collect_settings(
    project_root,
    vsdevcmd,
    cmake_path,
    arch,
    configure_preset,
    build_preset,
    fresh,
    cleanup_before_copy,
    sync_headers,
    patch_after_configure,
    patch_before_build,
) -> dict:
    return {
        "project_root": project_root,
        "vsdevcmd": vsdevcmd,
        "cmake_path": cmake_path,
        "arch": arch,
        "configure_preset": configure_preset,
        "build_preset": build_preset,
        "fresh": fresh,
        "cleanup_before_copy": cleanup_before_copy,
        "sync_headers": sync_headers,
        "patch_after_configure": patch_after_configure,
        "patch_before_build": patch_before_build,
    }


def default_values() -> dict:
    saved = load_saved_settings()
    auto_root = auto_find_project_root(Path.cwd())
    auto_root_str = str(auto_root) if auto_root else DEFAULT_PROJECT_ROOT
    saved_root = str(saved.get("project_root", "") or "").strip()
    if saved_root and Path(saved_root).expanduser().exists():
        project_root_value = saved_root
    else:
        project_root_value = auto_root_str

    return {
        "project_root": project_root_value,
        "vsdevcmd": saved.get("vsdevcmd", DEFAULT_VSDEVCMD),
        "cmake_path": saved.get("cmake_path", DEFAULT_CMAKE),
        "arch": saved.get("arch", "x64"),
        "configure_preset": saved.get("configure_preset", DEFAULT_CONFIGURE_PRESET),
        "build_preset": saved.get("build_preset", DEFAULT_BUILD_PRESET),
        "fresh": saved.get("fresh", True),
        "cleanup_before_copy": saved.get("cleanup_before_copy", True),
        "sync_headers": saved.get("sync_headers", True),
        "patch_after_configure": saved.get("patch_after_configure", True),
        "patch_before_build": saved.get("patch_before_build", True),
    }


# ─────────────────────────────────────────────────────────────
# Action implementations
# ─────────────────────────────────────────────────────────────

def do_file_prepare(
    src_dir,
    src_cmake,
    c_files,
    h_files,
    cleanup_before_copy,
    sync_headers,
    log,
) -> str:
    if not c_files:
        raise ValueError("请至少上传 1 个 C 文件")
    check_duplicate_basenames(c_files, h_files)

    if cleanup_before_copy:
        cleanup_src(src_dir, log)

    copy_files_to_src(src_dir, c_files, h_files, log)
    preview = update_src_cmakelists(src_cmake, c_files, h_files, sync_headers, log)
    log.append("[文件] 处理完成")
    return preview


def do_configure(root, vsdevcmd, cmake_path, arch, configure_preset, fresh, log) -> None:
    chain = make_configure_chain(vsdevcmd, cmake_path, arch, configure_preset, fresh)
    log.append(f"[命令] cmd.exe /d /c {chain}")
    code, out = run_cmd_chain(chain, cwd=root)
    if out.strip():
        log.append(out.rstrip())
    if code != 0:
        raise RuntimeError(f"配置失败，返回码: {code}")
    log.append("[配置] 完成")


def do_patch(udf_names, log) -> str:
    changed, report = patch_udf_names(udf_names)
    if changed > 0:
        log.append(f"[补丁] 已修复 {changed} 处缺失 ';' 的 extern DEFINE_* 行")
    else:
        log.append("[补丁] 未发现需要修复的 extern DEFINE_* 行")
    return report


def do_build(root, vsdevcmd, cmake_path, arch, build_preset, log) -> None:
    chain = make_build_chain(vsdevcmd, cmake_path, arch, build_preset)
    log.append(f"[命令] cmd.exe /d /c {chain}")
    code, out = run_cmd_chain(chain, cwd=root)
    if out.strip():
        log.append(out.rstrip())
    if code != 0:
        raise RuntimeError(f"构建失败，返回码: {code}")
    log.append("[构建] 完成")


# ─────────────────────────────────────────────────────────────
# UI rendering helpers
# ─────────────────────────────────────────────────────────────

def _esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def make_status_html(text: str) -> str:
    with EXTERNAL_BRIDGE_LOCK:
        pct = float(PROGRESS_STATE.get("pct", 0.0) or 0.0)
        running = bool(PROGRESS_STATE.get("running", False))

    pct = max(0.0, min(1.0, pct))
    pct_text = f"{int(round(pct * 100))}%"

    if running:
        prog_cls = "status-prog-running"
    elif pct >= 1.0:
        prog_cls = "status-prog-done"
    else:
        prog_cls = "status-prog-idle"

    progress_html = f"""
      <div class="status-progress-row {prog_cls}">
        <div class="status-progress-track">
          <div class="status-progress-fill" style="width:{pct_text};"></div>
        </div>
        <div class="status-progress-pct">{_esc(pct_text)}</div>
      </div>
    """

    if not text:
        return """
        <div class="status-box status-idle">
          <div class="status-badge">等待执行</div>
          <div class="status-main">当前尚未开始执行任务</div>
          <div class="status-sub">点击下方操作按钮后，这里会显示总体执行结果。</div>
          <div class="status-progress-row status-prog-idle">
            <div class="status-progress-track">
              <div class="status-progress-fill" style="width:0%;"></div>
            </div>
            <div class="status-progress-pct">0%</div>
          </div>
        </div>
        """

    t = _esc(text)
    if "成功" in text:
        cls = "status-success"
        badge = "执行成功"
    elif "失败" in text or "错误" in text:
        cls = "status-error"
        badge = "执行失败"
    else:
        cls = "status-info"
        badge = "状态更新"

    return f"""
    <div class="status-box {cls}">
      <div class="status-badge">{badge}</div>
      <div class="status-main">{t}</div>
      <div class="status-sub">文件处理、配置、补丁、构建的执行结果已汇总到下方各区域。</div>
      {progress_html}
    </div>
    """


def make_summary_cards_html(log: str, action: str) -> str:
    copy_count = log.count("[复制]")
    cleanup_count = log.count("[清理]")
    patch_count = 0
    m = re.search(r"\[补丁\] 已修复 (\d+) 处", log)
    if m:
        patch_count = int(m.group(1))

    configure_state = "已完成" if "[配置] 完成" in log else ("失败" if "配置失败" in log else "未执行")
    build_state = "已完成" if "[构建] 完成" in log else ("失败" if "构建失败" in log else "未执行")

    return f"""
    <div class="summary-grid">
      <div class="summary-card">
        <div class="summary-label">当前动作</div>
        <div class="summary-value">{_esc(action)}</div>
      </div>
      <div class="summary-card">
        <div class="summary-label">复制文件数</div>
        <div class="summary-value">{copy_count}</div>
      </div>
      <div class="summary-card">
        <div class="summary-label">清理文件数</div>
        <div class="summary-value">{cleanup_count}</div>
      </div>
      <div class="summary-card">
        <div class="summary-label">补丁修复数</div>
        <div class="summary-value">{patch_count}</div>
      </div>
      <div class="summary-card">
        <div class="summary-label">配置阶段</div>
        <div class="summary-value">{_esc(configure_state)}</div>
      </div>
      <div class="summary-card">
        <div class="summary-label">构建阶段</div>
        <div class="summary-value">{_esc(build_state)}</div>
      </div>
    </div>
    """


def make_pipeline_html(log: str, action: str) -> str:
    active = {
        "仅处理文件": {"file"},
        "仅执行配置": {"configure"},
        "仅执行补丁": {"patch"},
        "仅执行构建": {"build"},
        "一键执行": {"file", "configure", "patch", "build"},
    }.get(action, {"file", "configure", "patch", "build"})

    steps = {
        "file": {"title": "文件处理", "desc": "上传、清理、复制，并更新 src/CMakeLists.txt"},
        "configure": {"title": "CMake 配置", "desc": "调用 VsDevCmd 与 cmake --preset 完成配置"},
        "patch": {"title": "补丁修复", "desc": "检查并修补 udf_names.c 中 extern DEFINE_* 缺失分号"},
        "build": {"title": "CMake 构建", "desc": "调用 cmake --build --preset 完成最终构建"},
    }

    state = {}
    for key in steps:
        if key not in active:
            state[key] = ("跳过", "stage-skipped", "本次操作不包含该阶段")
        else:
            state[key] = ("待执行", "stage-pending", "尚未执行")

    if log:
        if "file" in active:
            if "[文件] 处理完成" in log:
                cnt = log.count("[复制]")
                state["file"] = ("完成", "stage-success", f"已复制 {cnt} 个文件")
            elif "[错误]" in log and any(k in log for k in ["请至少上传", "重名", "未找到", "不存在"]):
                state["file"] = ("失败", "stage-error", "文件处理阶段发生错误")

        if "configure" in active:
            if "[配置] 完成" in log:
                state["configure"] = ("完成", "stage-success", "cmake configure 已完成")
            elif "配置失败" in log or "Configuring incomplete" in log:
                state["configure"] = ("失败", "stage-error", "配置阶段失败，请查看错误摘要")

        if "patch" in active:
            if "[补丁] 已修复" in log:
                m = re.search(r"\[补丁\] 已修复 (\d+) 处", log)
                detail = f"已修复 {m.group(1)} 处问题" if m else "已修复若干问题"
                state["patch"] = ("已修复", "stage-warning", detail)
            elif "[补丁] 未发现" in log:
                state["patch"] = ("完成", "stage-success", "未发现需要修复的问题")

        if "build" in active:
            if "[构建] 完成" in log:
                state["build"] = ("完成", "stage-success", "构建成功结束")
            elif "构建失败" in log:
                state["build"] = ("失败", "stage-error", "构建失败，请查看错误摘要")

    cards = []
    order = ["file", "configure", "patch", "build"]
    for idx, key in enumerate(order, start=1):
        title = steps[key]["title"]
        desc = steps[key]["desc"]
        label, cls, detail = state[key]
        cards.append(
            f"""
            <div class="{cls} stage-card">
              <div class="stage-head">
                <div class="stage-index">Step {idx}</div>
                <div class="stage-state">{label}</div>
              </div>
              <div class="stage-title">{title}</div>
              <div class="stage-desc">{_esc(desc)}</div>
              <div class="stage-detail">{_esc(detail)}</div>
            </div>
            """
        )

    return f"""
    <div class="panel-shell">
      <div class="panel-title">阶段进度</div>
      <div class="stage-grid">
        {''.join(cards)}
      </div>
    </div>
    """


def make_errors_html(errors: str) -> str:
    if not errors or errors == "未提取到明显的 error / failed 行。":
        return """
        <div class="result-box result-ok">
          <div class="result-title">错误摘要</div>
          <div class="result-main">未检测到明显错误行</div>
          <div class="result-sub">如果构建结果仍不符合预期，可展开完整日志继续检查。</div>
        </div>
        """

    lines = errors.splitlines()
    items = "".join(
        f'<div class="error-line">{_esc(line)}</div>'
        for line in lines[:60]
    )
    more = (
        f'<div class="error-more">... 还有 {len(lines) - 60} 行未展开</div>'
        if len(lines) > 60 else ""
    )

    return f"""
    <div class="result-box result-warn">
      <div class="result-title">错误摘要</div>
      <div class="result-main">检测到 {len(lines)} 条 error / failed 相关信息</div>
      <div class="error-list">
        {items}
        {more}
      </div>
    </div>
    """


def make_diagnostics_html(diagnostics: str) -> str:
    if not diagnostics:
        return """
        <div class="panel-shell">
          <div class="panel-title">即时诊断</div>
          <div class="empty-note">执行后这里会显示当前流程的总结判断。</div>
        </div>
        """

    rows = []
    for line in diagnostics.splitlines():
        clean = line.lstrip("- ").strip()
        if not clean:
            continue

        if any(k in clean for k in ["成功", "完成"]):
            cls = "diag-ok"
            tag = "完成"
        elif any(k in clean for k in ["失败", "错误", "仍有"]):
            cls = "diag-error"
            tag = "异常"
        elif any(k in clean for k in ["补丁", "修复", "已补"]):
            cls = "diag-warn"
            tag = "修复"
        else:
            cls = "diag-info"
            tag = "信息"

        rows.append(
            f"""
            <div class="diag-row {cls}">
              <div class="diag-tag">{tag}</div>
              <div class="diag-text">{_esc(clean)}</div>
            </div>
            """
        )

    return f"""
    <div class="panel-shell">
      <div class="panel-title">即时诊断</div>
      <div class="diag-list">
        {''.join(rows)}
      </div>
    </div>
    """


def make_empty_preview_html() -> str:
    return """
    <div class="empty-note">
      执行后这里会显示将写入 <code>src/CMakeLists.txt</code> 的核心内容预览。
    </div>
    """


# ─────────────────────────────────────────────────────────────
# Main orchestrator
# ─────────────────────────────────────────────────────────────

def run_action(
    action: str,
    project_root: str,
    vsdevcmd: str,
    cmake_path: str,
    arch: str,
    configure_preset: str,
    build_preset: str,
    fresh: bool,
    cleanup_before_copy: bool,
    sync_headers: bool,
    patch_after_configure: bool,
    patch_before_build: bool,
    c_uploads,
    h_uploads,
    progress=None,
):
    log: list[str] = []
    cmake_preview = ""
    patch_report = "尚未执行补丁。"

    def _prog(pct: float, desc: str = ""):
        _set_progress_state(action=action, pct=pct, desc=desc, running=(pct < 1.0))
        if callable(progress):
            try:
                progress(pct, desc=desc)
            except Exception:
                pass

    _prog(0.0, "初始化参数…")

    settings = collect_settings(
        project_root=project_root,
        vsdevcmd=vsdevcmd,
        cmake_path=cmake_path,
        arch=arch,
        configure_preset=(configure_preset or "").strip(),
        build_preset=((build_preset or configure_preset or "").strip()),
        fresh=fresh,
        cleanup_before_copy=cleanup_before_copy,
        sync_headers=sync_headers,
        patch_after_configure=patch_after_configure,
        patch_before_build=patch_before_build,
    )
    save_settings(settings)

    configure_choices, build_choices = load_preset_names(project_root)
    configure_value = settings["configure_preset"] or (
        configure_choices[0] if configure_choices else ""
    )
    build_value = settings["build_preset"] or (
        build_choices[0] if build_choices else configure_value
    )

    command_preview = build_command_preview(
        vsdevcmd=settings["vsdevcmd"],
        cmake_path=settings["cmake_path"],
        arch=settings["arch"],
        configure_preset=configure_value,
        build_preset=build_value,
        fresh=settings["fresh"],
    )

    def _pack(label: str):
        full_log = "\n".join(log).strip()
        diag_text = make_diagnostics(full_log, patch_report, project_root)
        errors_text = extract_errors(full_log)
        return (
            make_status_html(label),
            make_summary_cards_html(full_log, action),
            make_pipeline_html(full_log, action),
            make_diagnostics_html(diag_text),
            cmake_preview,
            command_preview,
            patch_report,
            make_errors_html(errors_text),
            full_log,
            json.dumps(settings, ensure_ascii=False, indent=2),
            gr.update(choices=configure_choices, value=configure_value),
            gr.update(choices=build_choices, value=build_value),
        )

    try:
        _prog(0.08, "验证工程目录…")
        root, src_dir, src_cmake, udf_names = validate_project(project_root)
        c_files = normalize_uploaded_files(c_uploads)
        h_files = normalize_uploaded_files(h_uploads)

        if action in {"仅处理文件", "一键执行"}:
            _prog(0.15, "处理并复制源文件…")
            cmake_preview = do_file_prepare(
                src_dir,
                src_cmake,
                c_files,
                h_files,
                cleanup_before_copy,
                sync_headers,
                log,
            )
            _prog(0.35, "文件处理完成")
        else:
            cmake_preview = "未执行文件处理，保持当前 src/CMakeLists.txt 状态。"

        if action in {"仅执行配置", "一键执行"}:
            _prog(0.40, "执行 CMake 配置…")
            do_configure(root, vsdevcmd, cmake_path, arch, configure_value, fresh, log)
            _prog(0.65, "配置完成")
            if patch_after_configure:
                _prog(0.68, "修补 udf_names.c…")
                patch_report = do_patch(udf_names, log)
                _prog(0.73, "补丁完成")

        if action == "仅执行补丁":
            _prog(0.40, "修补 udf_names.c…")
            patch_report = do_patch(udf_names, log)
            _prog(0.80, "补丁完成")

        if action in {"仅执行构建", "一键执行"}:
            if patch_before_build and not (action == "一键执行" and patch_after_configure):
                _prog(0.73, "构建前补丁检查…")
                patch_report = do_patch(udf_names, log)
            _prog(0.78, "执行 CMake 构建…")
            do_build(root, vsdevcmd, cmake_path, arch, build_value, log)
            _prog(1.0, "构建完成")

        _prog(1.0, "全部完成")
        _set_progress_state(action=action, pct=1.0, desc="全部完成", running=False)
        return _pack(f"{action}：成功")

    except Exception as exc:
        log.append(f"[错误] {exc}")
        _prog(1.0, "执行中断")
        _set_progress_state(action=action, pct=1.0, desc=f"执行中断：{exc}", running=False)
        return _pack(f"{action}：失败 — {exc}")


# ─────────────────────────────────────────────────────────────
# Scan / preview helpers
# ─────────────────────────────────────────────────────────────

def scan_presets(project_root: str, configure_preset: str, build_preset: str):
    cfg, bld = load_preset_names(project_root)
    status = []

    if cfg:
        status.append("✅ configure presets: " + ", ".join(cfg))
    if bld:
        status.append("✅ build presets: " + ", ".join(bld))
    if not status:
        status.append("⚠️ 未扫描到 CMakePresets.json / CMakeUserPresets.json 中的 preset。")

    cfg_value = configure_preset if configure_preset in cfg else (cfg[0] if cfg else configure_preset)
    bld_value = build_preset if build_preset in bld else (bld[0] if bld else build_preset or cfg_value)

    return (
        "\n".join(status),
        gr.update(choices=cfg, value=cfg_value),
        gr.update(choices=bld, value=bld_value),
    )


def auto_detect_and_scan_presets(project_root: str, configure_preset: str, build_preset: str):
    found = auto_find_project_root(Path.cwd())
    if not found:
        return (
            "⚠️ 在当前工作目录下未找到可用工程（需要同时具备 CMakePresets.json + CMakeLists + src/CMakeLists.txt）。",
            gr.update(value=project_root),
            gr.update(),
            gr.update(),
        )

    found_str = str(found)
    scan_text, cfg_update, bld_update = scan_presets(found_str, configure_preset, build_preset)
    return (
        f"✅ 已自动定位工程目录: {found_str}\n{scan_text}",
        gr.update(value=found_str),
        cfg_update,
        bld_update,
    )


def preview_commands(vsdevcmd, cmake_path, arch, configure_preset, build_preset, fresh):
    return build_command_preview(
        vsdevcmd,
        cmake_path,
        arch,
        configure_preset,
        build_preset or configure_preset,
        fresh,
    )


# ─────────────────────────────────────────────────────────────
# Action wrappers
# ─────────────────────────────────────────────────────────────

def action_prepare(*args):
    result = run_action("仅处理文件", *args, progress=None)
    status_html, _, _, _, _, _, _, _, full_log, _, _, _ = result
    c_files = [str(p) for p in normalize_uploaded_files(args[11])] if len(args) > 11 else []
    h_files = [str(p) for p in normalize_uploaded_files(args[12])] if len(args) > 12 else []
    _set_ui_snapshot(result, c_files=c_files, h_files=h_files)
    _set_bridge_state(
        source="webui",
        status=_strip_html(status_html),
        ok="：成功" in status_html,
        log=full_log,
    )
    return result


def action_configure(*args):
    result = run_action("仅执行配置", *args, progress=None)
    status_html, _, _, _, _, _, _, _, full_log, _, _, _ = result
    c_files = [str(p) for p in normalize_uploaded_files(args[11])] if len(args) > 11 else []
    h_files = [str(p) for p in normalize_uploaded_files(args[12])] if len(args) > 12 else []
    _set_ui_snapshot(result, c_files=c_files, h_files=h_files)
    _set_bridge_state(
        source="webui",
        status=_strip_html(status_html),
        ok="：成功" in status_html,
        log=full_log,
    )
    return result


def action_patch_only(*args):
    result = run_action("仅执行补丁", *args, progress=None)
    status_html, _, _, _, _, _, _, _, full_log, _, _, _ = result
    c_files = [str(p) for p in normalize_uploaded_files(args[11])] if len(args) > 11 else []
    h_files = [str(p) for p in normalize_uploaded_files(args[12])] if len(args) > 12 else []
    _set_ui_snapshot(result, c_files=c_files, h_files=h_files)
    _set_bridge_state(
        source="webui",
        status=_strip_html(status_html),
        ok="：成功" in status_html,
        log=full_log,
    )
    return result


def action_build(*args):
    result = run_action("仅执行构建", *args, progress=None)
    status_html, _, _, _, _, _, _, _, full_log, _, _, _ = result
    c_files = [str(p) for p in normalize_uploaded_files(args[11])] if len(args) > 11 else []
    h_files = [str(p) for p in normalize_uploaded_files(args[12])] if len(args) > 12 else []
    _set_ui_snapshot(result, c_files=c_files, h_files=h_files)
    _set_bridge_state(
        source="webui",
        status=_strip_html(status_html),
        ok="：成功" in status_html,
        log=full_log,
    )
    return result


def action_run_all(*args):
    result = run_action("一键执行", *args, progress=None)
    status_html, _, _, _, _, _, _, _, full_log, _, _, _ = result
    c_files = [str(p) for p in normalize_uploaded_files(args[11])] if len(args) > 11 else []
    h_files = [str(p) for p in normalize_uploaded_files(args[12])] if len(args) > 12 else []
    _set_ui_snapshot(result, c_files=c_files, h_files=h_files)
    _set_bridge_state(
        source="webui",
        status=_strip_html(status_html),
        ok="：成功" in status_html,
        log=full_log,
    )
    return result


def run_all_from_external(
    c_file_paths: Iterable[str],
    h_file_paths: Iterable[str] | None = None,
    overrides: dict | None = None,
) -> dict:
    c_paths = [str(p).strip() for p in (c_file_paths or []) if str(p).strip()]
    h_paths = [str(p).strip() for p in (h_file_paths or []) if str(p).strip()]

    if not c_paths:
        raise ValueError("c_file_paths 不能为空，至少提供 1 个 .c 文件路径")

    for p in c_paths:
        path = Path(p)
        if path.suffix.lower() != ".c":
            raise ValueError(f"C 文件后缀必须是 .c: {p}")
        if not path.exists():
            raise FileNotFoundError(f"未找到 C 文件: {p}")

    for p in h_paths:
        path = Path(p)
        if path.suffix.lower() not in {".h", ".hpp"}:
            raise ValueError(f"头文件后缀必须是 .h 或 .hpp: {p}")
        if not path.exists():
            raise FileNotFoundError(f"未找到头文件: {p}")

    values = default_values()
    if overrides:
        allowed_keys = {
            "project_root",
            "vsdevcmd",
            "cmake_path",
            "arch",
            "configure_preset",
            "build_preset",
            "fresh",
            "cleanup_before_copy",
            "sync_headers",
            "patch_after_configure",
            "patch_before_build",
        }
        for key, value in overrides.items():
            if key in allowed_keys:
                values[key] = value

    result = run_action(
        action="一键执行",
        project_root=values["project_root"],
        vsdevcmd=values["vsdevcmd"],
        cmake_path=values["cmake_path"],
        arch=values["arch"],
        configure_preset=values["configure_preset"],
        build_preset=values["build_preset"],
        fresh=values["fresh"],
        cleanup_before_copy=values["cleanup_before_copy"],
        sync_headers=values["sync_headers"],
        patch_after_configure=values["patch_after_configure"],
        patch_before_build=values["patch_before_build"],
        c_uploads=c_paths,
        h_uploads=h_paths,
        progress=None,
    )

    status_html, _, _, _, cmake_preview, command_preview, patch_report, errors_html, full_log, settings_json, _, _ = result
    payload = {
        "ok": "：成功" in status_html,
        "status_html": status_html,
        "cmake_preview": cmake_preview,
        "command_preview": command_preview,
        "patch_report": patch_report,
        "errors_html": errors_html,
        "log": full_log,
        "settings_json": settings_json,
    }
    _set_ui_snapshot(result, c_files=c_paths, h_files=h_paths)
    _set_bridge_state(
        source="external-python",
        status=_strip_html(status_html),
        ok=payload["ok"],
        log=full_log,
    )
    return payload


def _parse_paths_input(raw: str | None) -> list[str]:
    value = (raw or "").strip()
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except Exception:
        pass
    return [item.strip() for item in value.splitlines() if item.strip()]


def http_run_all_api(c_files_input: str, h_files_input: str, overrides_input: str) -> dict:
    c_paths = _parse_paths_input(c_files_input)
    h_paths = _parse_paths_input(h_files_input)

    overrides = None
    raw_overrides = (overrides_input or "").strip()
    if raw_overrides:
        try:
            parsed = json.loads(raw_overrides)
            if isinstance(parsed, dict):
                overrides = parsed
            else:
                raise ValueError("overrides 必须是 JSON 对象")
        except Exception as exc:
            raise ValueError(f"overrides 解析失败: {exc}") from exc

    payload = run_all_from_external(
        c_file_paths=c_paths,
        h_file_paths=h_paths,
        overrides=overrides,
    )
    _set_bridge_state(
        source="http-api",
        status=_strip_html(payload.get("status_html", "")),
        ok=payload.get("ok"),
        log=payload.get("log", ""),
    )
    return payload


# ─────────────────────────────────────────────────────────────
# UI fragments
# ─────────────────────────────────────────────────────────────

def page_header_html() -> str:
    return """
    <div class="hero-card">
      <div class="hero-top">
        <div class="hero-title">Fluent UDF 编译工具</div>
        <div class="hero-tag">Gradio · CMake Presets · UDF Patch</div>
      </div>
      <div class="hero-sub">
        面向 Fluent UDF 的文件准备、CMake 配置、补丁修复与构建一体化操作面板。
      </div>
      <div class="hero-flow">
        <span>文件处理</span>
        <span class="flow-sep">→</span>
        <span>CMake 配置</span>
        <span class="flow-sep">→</span>
        <span>udf_names.c 补丁</span>
        <span class="flow-sep">→</span>
        <span>CMake 构建</span>
      </div>
    </div>
    """


def section_title_html(title: str, desc: str = "") -> str:
    desc_html = f'<div class="section-desc">{_esc(desc)}</div>' if desc else ""
    return f"""
    <div class="section-head">
      <div class="section-title">{_esc(title)}</div>
      {desc_html}
    </div>
    """


# ─────────────────────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────────────────────

def create_app() -> gr.Blocks:
    dv = default_values()
    cfg_presets, bld_presets = load_preset_names(dv["project_root"])

    css = """
    :root {
      --app-radius-xl: 18px;
      --app-radius-lg: 14px;
      --app-radius-md: 10px;
      --app-gap: 14px;
    }

    .gradio-container {
      max-width: 96% !important;
      padding-top: 18px !important;
      padding-bottom: 22px !important;
    }

    .app-shell {
      gap: 14px;
    }

    .hero-card {
      border: 1px solid var(--border-color-primary);
      background: var(--block-background-fill);
      border-radius: var(--app-radius-xl);
      padding: 20px 22px;
      box-shadow: var(--shadow-drop);
      margin-bottom: 6px;
    }

    .hero-top {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
      margin-bottom: 8px;
    }

    .hero-title {
      font-size: 1.55rem;
      font-weight: 800;
      color: var(--body-text-color);
      letter-spacing: 0.2px;
    }

    .hero-tag {
      font-size: 0.78rem;
      padding: 5px 10px;
      border-radius: 999px;
      border: 1px solid var(--border-color-primary);
      background: var(--block-label-background-fill);
      color: var(--body-text-color-subdued);
      font-weight: 600;
    }

    .hero-sub {
      color: var(--body-text-color-subdued);
      line-height: 1.7;
      font-size: 0.92rem;
      margin-bottom: 12px;
    }

    .hero-flow {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      color: var(--body-text-color);
      font-size: 0.86rem;
      font-weight: 600;
    }

    .hero-flow span {
      padding: 6px 10px;
      border-radius: 999px;
      background: var(--block-label-background-fill);
      border: 1px solid var(--border-color-primary);
    }

    .hero-flow .flow-sep {
      padding: 0;
      background: transparent;
      border: none;
      color: var(--body-text-color-subdued);
    }

    .section-head {
      margin: 4px 0 10px 0;
    }

    .section-title {
      font-size: 1rem;
      font-weight: 800;
      color: var(--body-text-color);
      line-height: 1.4;
    }

    .section-desc {
      margin-top: 4px;
      font-size: 0.84rem;
      color: var(--body-text-color-subdued);
      line-height: 1.6;
    }

    .panel-shell {
      border: 1px solid var(--border-color-primary);
      background: var(--block-background-fill);
      border-radius: var(--app-radius-lg);
      padding: 14px;
      box-shadow: var(--shadow-drop);
    }

    .panel-title {
      font-size: 0.92rem;
      font-weight: 800;
      color: var(--body-text-color);
      margin-bottom: 12px;
      padding-bottom: 10px;
      border-bottom: 1px solid var(--border-color-primary);
    }

    .summary-grid {
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 10px;
    }

    .summary-card {
      border: 1px solid var(--border-color-primary);
      background: var(--block-label-background-fill);
      border-radius: var(--app-radius-md);
      padding: 12px 12px 10px 12px;
      min-height: 78px;
    }

    .summary-label {
      font-size: 0.76rem;
      color: var(--body-text-color-subdued);
      margin-bottom: 6px;
    }

    .summary-value {
      font-size: 1rem;
      font-weight: 800;
      color: var(--body-text-color);
      line-height: 1.4;
      word-break: break-word;
    }

    .status-box {
      border-radius: var(--app-radius-lg);
      border: 1px solid var(--border-color-primary);
      background: var(--block-background-fill);
      padding: 16px 18px;
      box-shadow: var(--shadow-drop);
    }

    .status-badge {
      display: inline-block;
      padding: 4px 9px;
      border-radius: 999px;
      font-size: 0.74rem;
      font-weight: 800;
      margin-bottom: 8px;
      border: 1px solid var(--border-color-primary);
      background: var(--block-label-background-fill);
      color: var(--body-text-color-subdued);
    }

    .status-main {
      font-size: 1.02rem;
      font-weight: 800;
      color: var(--body-text-color);
      line-height: 1.55;
    }

    .status-sub {
      margin-top: 6px;
      color: var(--body-text-color-subdued);
      font-size: 0.84rem;
      line-height: 1.7;
    }

        .status-success {
            background: var(--block-label-background-fill);
            border-color: var(--button-primary-border-color);
        }

        .status-error {
            background: var(--error-background-fill);
            border-color: var(--error-border-fill);
        }

        .status-info {
            background: var(--block-background-fill);
            border-color: var(--border-color-primary);
        }

        .status-idle {
            background: var(--background-fill-primary);
            border-color: var(--border-color-primary);
        }

        .status-success .status-badge,
        .status-success .status-main,
        .status-error .status-badge,
        .status-error .status-main,
        .status-info .status-badge,
        .status-info .status-main,
        .status-idle .status-badge,
        .status-idle .status-main {
            color: var(--body-text-color);
        }

    .stage-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }

    .stage-card {
      border-radius: var(--app-radius-md);
      border: 1px solid var(--border-color-primary);
      background: var(--background-fill-primary);
      padding: 13px;
      min-height: 138px;
    }

    .stage-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
      margin-bottom: 10px;
    }

    .stage-index {
      font-size: 0.73rem;
      font-weight: 800;
      padding: 4px 8px;
      border-radius: 999px;
      border: 1px solid var(--border-color-primary);
      background: var(--block-background-fill);
      color: var(--body-text-color-subdued);
    }

    .stage-state {
      font-size: 0.76rem;
      font-weight: 800;
      color: var(--body-text-color-subdued);
    }

    .stage-title {
      font-size: 0.95rem;
      font-weight: 800;
      color: var(--body-text-color);
      margin-bottom: 6px;
    }

    .stage-desc {
      font-size: 0.81rem;
      color: var(--body-text-color-subdued);
      line-height: 1.6;
      margin-bottom: 10px;
    }

    .stage-detail {
      font-size: 0.83rem;
      color: var(--body-text-color);
      font-weight: 600;
      line-height: 1.6;
    }

    .stage-success {
        outline: 2px solid var(--border-color-primary);
        background: var(--block-label-background-fill);
    }

    .stage-warning {
        outline: 2px solid var(--error-background-fill);
        background: var(--block-background-fill);
    }

    .stage-error {
        outline: 2px solid var(--error-border-fill);
        background: var(--error-background-fill);
    }

    .stage-pending {
        background: var(--block-background-fill);
        opacity: 0.92;
    }

    .stage-skipped {
        background: var(--block-background-fill);
        opacity: 0.65;
    }

    .diag-list {
      display: flex;
      flex-direction: column;
      gap: 9px;
    }

    .diag-row {
      display: flex;
      align-items: flex-start;
      gap: 10px;
      border: 1px solid var(--border-color-primary);
      background: var(--block-label-background-fill);
      border-radius: 10px;
      padding: 10px 11px;
    }

    .diag-tag {
      flex-shrink: 0;
      min-width: 46px;
      text-align: center;
      font-size: 0.72rem;
      font-weight: 800;
      padding: 4px 6px;
      border-radius: 999px;
      border: 1px solid var(--border-color-primary);
      background: var(--block-background-fill);
      color: var(--body-text-color-subdued);
    }

    .diag-text {
      font-size: 0.84rem;
      line-height: 1.65;
      color: var(--body-text-color);
    }

    .result-box {
      border-radius: var(--app-radius-lg);
      border: 1px solid var(--border-color-primary);
      background: var(--block-background-fill);
      padding: 14px;
      box-shadow: var(--shadow-drop);
    }

    .result-title {
      font-size: 0.9rem;
      font-weight: 800;
      color: var(--body-text-color);
      margin-bottom: 10px;
    }

    .result-main {
      font-size: 0.93rem;
      font-weight: 700;
      color: var(--body-text-color);
      margin-bottom: 6px;
      line-height: 1.6;
    }

    .result-sub {
      font-size: 0.82rem;
      color: var(--body-text-color-subdued);
      line-height: 1.65;
    }

    .error-list {
      max-height: 300px;
      overflow-y: auto;
      margin-top: 10px;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .error-line {
      font-family: Consolas, "Courier New", monospace;
      font-size: 0.78rem;
      line-height: 1.55;
      white-space: pre-wrap;
      word-break: break-all;
      border-radius: 8px;
      border: 1px solid var(--border-color-primary);
      background: var(--block-label-background-fill);
      padding: 7px 9px;
      color: var(--body-text-color);
    }

    .error-more {
      font-size: 0.78rem;
      color: var(--body-text-color-subdued);
      padding: 4px 2px 0 2px;
    }

    .empty-note {
      border: 1px dashed var(--border-color-primary);
      background: var(--block-label-background-fill);
      border-radius: 10px;
      padding: 14px 15px;
      color: var(--body-text-color-subdued);
      font-size: 0.84rem;
      font-style: italic;
      line-height: 1.7;
    }

    .soft-note {
      border: 1px solid var(--border-color-primary);
      background: var(--block-background-fill);
      border-radius: 12px;
      padding: 12px 14px;
      color: var(--body-text-color-subdued);
      font-size: 0.85rem;
      line-height: 1.7;
    }

    .toolbar-note {
      font-size: 0.82rem;
      color: var(--body-text-color-subdued);
      line-height: 1.6;
      margin-bottom: 8px;
    }

    .log-mono textarea,
    .cmd-mono textarea,
    .json-mono textarea {
      font-family: Consolas, "Courier New", monospace !important;
      line-height: 1.58 !important;
      font-size: 0.82rem !important;
    }

    .run-btn button,
    .core-btn button {
      font-weight: 800 !important;
    }

    .tab-nav button {
      font-weight: 700 !important;
      font-size: 0.92rem !important;
    }

        .status-progress-row {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-top: 10px;
        }

        .status-progress-track {
            flex: 1;
            width: 100%;
            height: 12px;
            border-radius: 999px;
            background: var(--background-fill-primary);
            border: 1px solid var(--border-color-primary);
            overflow: hidden;
        }

        .status-progress-fill {
            height: 100%;
            border-radius: 999px;
            background: var(--button-primary-background-fill);
            transition: width 0.25s ease;
        }

        .status-prog-done .status-progress-fill {
            background: var(--button-primary-background-fill-hover);
        }

        .status-prog-idle .status-progress-fill {
            background: var(--border-color-primary);
        }

        .status-error .status-progress-fill {
            background: var(--error-border-fill);
        }

        .status-success .status-progress-fill {
            background: var(--button-primary-background-fill-hover);
        }

        .status-progress-pct {
            font-size: 0.86rem;
            font-weight: 800;
            color: var(--body-text-color);
            min-width: 44px;
            text-align: right;
        }

        .files-compact .file-preview-holder,
        .files-compact .file-preview,
        .files-compact .file-list,
        .files-compact .file-upload-preview {
            max-height: 220px !important;
            overflow-y: auto !important;
        }

    @media (max-width: 1100px) {
      .summary-grid {
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }
    }

    @media (max-width: 820px) {
      .summary-grid,
      .stage-grid {
        grid-template-columns: 1fr;
      }
    }
    """

    launch_theme = gr.themes.Soft()

    with gr.Blocks(
        title="Fluent UDF 编译工具",
    ) as demo:
        gr.HTML(page_header_html())

        with gr.Row(equal_height=False):
            with gr.Column(scale=1, min_width=460):
                with gr.Tab("① 工程配置"):
                    gr.HTML(section_title_html(
                        "工程与工具链",
                        "先确认CMakeList目录、VsDevCmd、cmake 路径以及架构参数。"
                    ))

                    with gr.Column():
                        with gr.Row():
                            project_root = gr.Textbox(
                                label="CMakeList 目录",
                                value=dv["project_root"],
                                scale=5,
                                placeholder="例如：D:/MyUDFProject",
                            )
                            arch = gr.Dropdown(
                                label="目标架构",
                                choices=["x64", "x86", "arm64"],
                                value=dv["arch"],
                                scale=1,
                            )

                        vsdevcmd = gr.Textbox(
                            label="VsDevCmd.bat 路径",
                            value=dv["vsdevcmd"],
                            scale=1,
                        )
                        cmake_path = gr.Textbox(
                            label="cmake.exe 路径",
                            value=dv["cmake_path"],
                            scale=1,
                        )

                    gr.HTML(section_title_html(
                        "CMake Presets",
                        "扫描工程目录下的 CMakePresets.json / CMakeUserPresets.json，并同步到下拉框。"
                    ))

                    
                    with gr.Accordion(open=True):
                        with gr.Row():
                            scan_btn = gr.Button("扫描 Presets", variant="secondary", scale=1)
                            auto_detect_btn = gr.Button("自动搜索并填充目录", variant="secondary", scale=1)
                        
                        with gr.Row():
                            configure_preset = gr.Dropdown(
                                label="Configure Preset",
                                choices=cfg_presets,
                                value=dv["configure_preset"],
                                allow_custom_value=True,
                                scale=2,
                            )
                            build_preset = gr.Dropdown(
                                label="Build Preset",
                                choices=bld_presets,
                                value=dv["build_preset"],
                                allow_custom_value=True,
                                scale=2,
                            )
                        preset_scan_result = gr.Textbox(
                            label="扫描结果",
                            lines=2,
                            interactive=False,
                            scale=1,
                        )

                    gr.HTML(section_title_html(
                        "构建策略",
                        "文件清理、Header 同步、补丁触发时机等都会影响流程行为。"
                    ))

                    with gr.Row(equal_height=False):
                        with gr.Column():
                            #gr.Markdown("**配置 / 文件选项**")
                            fresh = gr.Checkbox(
                                label="配置时附加 --fresh（清理旧 CMake 缓存）",
                                value=dv["fresh"],
                            )
                            cleanup_before_copy = gr.Checkbox(
                                label="复制前清理旧 c / h / hpp 文件",
                                value=dv["cleanup_before_copy"],
                            )
                            sync_headers = gr.Checkbox(
                                label="同步写入 CHEADERS",
                                value=dv["sync_headers"],
                            )

                        with gr.Column():
                            # gr.Markdown("**补丁选项**")
                            patch_after_configure = gr.Checkbox(
                                label="配置完成后自动打补丁",
                                value=dv["patch_after_configure"],
                            )
                            patch_before_build = gr.Checkbox(
                                label="构建前再次检查补丁",
                                value=dv["patch_before_build"],
                            )

                    gr.HTML(section_title_html(
                        "命令预览",
                        "当前配置下将执行的命令链，用于执行前快速核对。"
                    ))
                    with gr.Row():
                        preview_cmd_btn = gr.Button("刷新命令预览", variant="secondary", scale=0)
                    command_preview = gr.Code(
                        label="命令预览",
                        language="shell",
                        lines=10,
                        elem_classes=["cmd-mono"],
                    )

                with gr.Tab("② 文件管理"):
                    gr.HTML(section_title_html(
                        "上传待编译文件",
                        "C 文件会写入 CSOURCES，头文件会复制到 src/ 并可同步写入 CHEADERS。"
                    ))

                    gr.HTML("""
                    <div class="soft-note">
                      上传后点击“仅处理文件”或“一键执行全流程”。<br>
                      文件处理阶段会按设置清理旧文件、复制新文件，并更新 <code>src/CMakeLists.txt</code>。
                    </div>
                    """)

                    folder_uploads = gr.Files(
                        label="文件夹上传（选择或拖入目录，自动筛选 .c/.h/.hpp）",
                        file_count="directory",
                        scale=1,
                        elem_classes=["files-compact"],
                    )
                    folder_scan_result = gr.Textbox(
                        label="文件夹自动筛选结果",
                        value="尚未选择文件夹。",
                        interactive=False,
                        lines=2,
                    )

                    with gr.Accordion("已选文件列表（数量多时可折叠）", open=True):
                        with gr.Row():
                            c_uploads = gr.Files(
                                label="待编译 C 文件（.c）",
                                file_count="multiple",
                                file_types=[".c"],
                                scale=1,
                                elem_classes=["files-compact"],
                            )
                            h_uploads = gr.Files(
                                label="头文件（.h / .hpp）",
                                file_count="multiple",
                                file_types=[".h", ".hpp"],
                                scale=1,
                                elem_classes=["files-compact"],
                            )

                    gr.HTML(section_title_html(
                        "将写入 src/CMakeLists.txt 的内容预览",
                        "执行文件处理后，会显示 CSOURCES / CHEADERS 的预览结果。"
                    ))
                    cmake_preview = gr.Code(
                        label="CMakeLists 写入预览",
                        language="shell",
                        lines=5,
                    )

            with gr.Column(scale=2):
                with gr.Tab("③ 执行与监控"):
                    gr.HTML(section_title_html(
                        "执行操作",
                        "支持单步执行，也支持一键完成从文件处理到构建的完整流程。"
                    ))
                    
                    with gr.Row():
                        btn_prepare = gr.Button(
                            "仅处理文件",
                            variant="secondary",
                            scale=1,
                            elem_classes=["core-btn"],
                        )
                        btn_configure = gr.Button(
                            "仅执行配置",
                            variant="secondary",
                            scale=1,
                            elem_classes=["core-btn"],
                        )
                        btn_patch = gr.Button(
                            "仅执行补丁",
                            variant="secondary",
                            scale=1,
                            elem_classes=["core-btn"],
                        )
                        btn_build = gr.Button(
                            "仅执行构建",
                            variant="secondary",
                            scale=1,
                            elem_classes=["core-btn"],
                        )
                    with gr.Row():
                        btn_run = gr.Button(
                            "一键执行全流程",
                            variant="primary",
                            scale=1,
                            elem_classes=["run-btn"],
                        )

                    status_html = gr.HTML(value=make_status_html(""))
                    summary_html = gr.HTML(value=make_summary_cards_html("", "一键执行"), visible=False)
                    pipeline_html = gr.HTML(value=make_pipeline_html("", "一键执行"))

                    with gr.Row(equal_height=True):
                        diagnostics_html = gr.HTML(value=make_diagnostics_html(""))
                        errors_html = gr.HTML(value=make_errors_html(""))

                    with gr.Column():
                        patch_report = gr.Textbox(
                            label="补丁报告",
                            lines=12,
                            interactive=False,
                        )
                        
                    with gr.Accordion("完整构建日志", open=False):
                        log = gr.Textbox(
                            label="日志",
                            lines=28,
                            max_lines=120,
                            interactive=False,
                            elem_classes=["log-mono"],
                        )

                    with gr.Accordion("已保存参数（JSON）", open=False):
                        settings_json = gr.Code(
                            label="参数 JSON",
                            language="json",
                            lines=16,
                            elem_classes=["json-mono"],
                        )
                    ui_seen_version = gr.State(0)

                with gr.Tab("④ HTTP 接口"):
                    gr.HTML(section_title_html(
                        "HTTP 触发一键流程",
                        "通过 Gradio API 触发，无需手动点击按钮；该接口执行结果会同步显示到“执行与监控”页。"
                    ))
                    gr.Markdown(
                        """
`POST /gradio_api/call/http_run_all`\n
参数按顺序传 3 个字符串：`c_files_input`、`h_files_input`、`overrides_input`。\n
其中 `c_files_input/h_files_input` 支持 JSON 数组或换行分隔路径；`overrides_input` 传 JSON 对象字符串。
"""
                    )
                    
                    external_bridge_html = gr.HTML(value=_bridge_state_html())

                    http_c_files_input = gr.Textbox(
                        label="c_files_input（JSON数组或换行路径）",
                        lines=4,
                        placeholder='["F:/pyFluent/testUDF.c"]',
                    )
                    http_h_files_input = gr.Textbox(
                        label="h_files_input（JSON数组或换行路径，可空）",
                        lines=3,
                        placeholder='["F:/pyFluent/udf_helper.h"]',
                    )
                    http_overrides_input = gr.Textbox(
                        label="overrides_input（JSON对象，可空）",
                        lines=5,
                        placeholder='{"project_root":"F:/udf-builder/CMake_Project_for_UDF"}',
                    )
                    http_trigger_btn = gr.Button("通过HTTP接口执行（本地测试）", variant="secondary")
                    http_result_json = gr.JSON(label="HTTP 返回结果")

        # Event wiring
        scan_btn.click(
            scan_presets,
            inputs=[project_root, configure_preset, build_preset],
            outputs=[preset_scan_result, configure_preset, build_preset],
        )

        auto_detect_btn.click(
            auto_detect_and_scan_presets,
            inputs=[project_root, configure_preset, build_preset],
            outputs=[preset_scan_result, project_root, configure_preset, build_preset],
        )

        preview_cmd_btn.click(
            preview_commands,
            inputs=[vsdevcmd, cmake_path, arch, configure_preset, build_preset, fresh],
            outputs=[command_preview],
        )

        folder_uploads.change(
            auto_collect_from_folder_upload,
            inputs=[folder_uploads, c_uploads, h_uploads],
            outputs=[c_uploads, h_uploads, folder_scan_result],
        )

        common_inputs = [
            project_root, vsdevcmd, cmake_path, arch,
            configure_preset, build_preset, fresh,
            cleanup_before_copy, sync_headers,
            patch_after_configure, patch_before_build,
            c_uploads, h_uploads,
        ]

        common_outputs = [
            status_html, summary_html, pipeline_html, diagnostics_html,
            cmake_preview, command_preview,
            patch_report, errors_html, log, settings_json,
            configure_preset, build_preset,
        ]

        btn_prepare.click(action_prepare, inputs=common_inputs, outputs=common_outputs)
        btn_configure.click(action_configure, inputs=common_inputs, outputs=common_outputs)
        btn_patch.click(action_patch_only, inputs=common_inputs, outputs=common_outputs)
        btn_build.click(action_build, inputs=common_inputs, outputs=common_outputs)
        btn_run.click(action_run_all, inputs=common_inputs, outputs=common_outputs)

        http_trigger_btn.click(
            http_run_all_api,
            inputs=[http_c_files_input, http_h_files_input, http_overrides_input],
            outputs=[http_result_json],
            api_name="http_run_all",
        )

        bridge_timer = gr.Timer(value=2.0)
        bridge_timer.tick(
            _pull_ui_sync,
            inputs=[ui_seen_version],
            outputs=[
                status_html, summary_html, pipeline_html, diagnostics_html,
                cmake_preview, command_preview,
                patch_report, errors_html, log, settings_json,
                c_uploads, h_uploads,
                external_bridge_html, ui_seen_version,
            ],
        )

        demo.load(
            preview_commands,
            inputs=[vsdevcmd, cmake_path, arch, configure_preset, build_preset, fresh],
            outputs=[command_preview],
        )

    demo._launch_css = css
    demo._launch_theme = launch_theme
    return demo


if __name__ == "__main__":
    app = create_app()
    extra_allowed = [item.strip() for item in os.getenv("UDF_ALLOWED_PATHS", "").split(";") if item.strip()]
    allowed_paths = [r"F:\\pyFluent", *extra_allowed]
    app.launch(
        inbrowser=True,
        css=getattr(app, "_launch_css", None),
        theme=getattr(app, "_launch_theme", None),
        allowed_paths=allowed_paths,
    )