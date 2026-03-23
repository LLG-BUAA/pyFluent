import json
import os
import time
from pathlib import Path

import requests

def _parse_paths_env(key: str, default_list: list[str]) -> list[str]:
    raw = (os.getenv(key, "") or "").strip()
    if not raw:
        return default_list

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except Exception:
        pass

    return [line.strip() for line in raw.splitlines() if line.strip()]


def _parse_overrides_env() -> dict:
    default_overrides = {"project_root": r"F:\udf-builder\CMake_Project_for_UDF"}
    raw = (os.getenv("UDF_WEB_OVERRIDES", "") or "").strip()
    if not raw:
        return default_overrides

    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("UDF_WEB_OVERRIDES 必须是 JSON 对象")
    return parsed


BASE = (os.getenv("UDF_WEB_BASE", "http://127.0.0.1:7860") or "").strip().rstrip("/")
C_FILES = _parse_paths_env("UDF_WEB_C_FILES", [r"F:\pyFluent\testUDF.c"])
H_FILES = _parse_paths_env("UDF_WEB_H_FILES", [])
OVERRIDES = _parse_overrides_env()

c_files_input = json.dumps(C_FILES, ensure_ascii=False)
h_files_input = json.dumps(H_FILES, ensure_ascii=False)
overrides_input = json.dumps(OVERRIDES, ensure_ascii=False)


def _validate_inputs() -> None:
    if not C_FILES:
        raise ValueError("未提供 C 文件，请设置 UDF_WEB_C_FILES")

    for item in C_FILES:
        path = Path(item)
        if path.suffix.lower() != ".c":
            raise ValueError(f"C 文件后缀必须是 .c: {item}")
        if not path.exists():
            raise FileNotFoundError(f"C 文件不存在: {item}")

    for item in H_FILES:
        path = Path(item)
        if path.suffix.lower() not in {".h", ".hpp"}:
            raise ValueError(f"头文件后缀必须是 .h/.hpp: {item}")
        if not path.exists():
            raise FileNotFoundError(f"头文件不存在: {item}")


def _print_effective_config() -> None:
    print("[web-client] BASE:", BASE)
    print("[web-client] C_FILES:", C_FILES)
    print("[web-client] H_FILES:", H_FILES)
    print("[web-client] OVERRIDES:", OVERRIDES)


def _safe_json(resp: requests.Response):
    ctype = (resp.headers.get("content-type") or "").lower()
    if "application/json" not in ctype:
        return None
    try:
        return resp.json()
    except Exception:
        return None


def _extract_result_from_sse(text: str):
    event_name = None
    data_lines = []
    for line in text.splitlines():
        if line.startswith("event:"):
            event_name = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data_lines.append(line.split(":", 1)[1].strip())

    if event_name != "complete" or not data_lines:
        return None

    raw = "\n".join(data_lines)
    try:
        payload = json.loads(raw)
        if isinstance(payload, dict) and "data" in payload and payload["data"]:
            return payload["data"][0]
    except Exception:
        pass
    return None


def _post_and_get_event_id() -> tuple[str, str]:
    endpoints = [
        "/gradio_api/call/http_run_all",
        "/api/call/http_run_all",
    ]

    last_error = ""
    for endpoint in endpoints:
        url = f"{BASE}{endpoint}"
        r = requests.post(
            url,
            json={"data": [c_files_input, h_files_input, overrides_input]},
            timeout=30,
        )
        payload = _safe_json(r)
        if r.status_code == 200 and isinstance(payload, dict) and payload.get("event_id"):
            return endpoint, payload["event_id"]

        preview = (r.text or "")[:220].replace("\n", " ")
        last_error = f"POST {url} 失败: status={r.status_code}, body={preview}"

    raise RuntimeError(last_error or "未找到可用 Gradio call 端点")


def main():
    _validate_inputs()
    _print_effective_config()

    endpoint, event_id = _post_and_get_event_id()
    poll_url = f"{BASE}{endpoint}/{event_id}"

    while True:
        r = requests.get(poll_url, timeout=30)
        if r.status_code != 200:
            preview = (r.text or "")[:220].replace("\n", " ")
            raise RuntimeError(f"轮询失败: status={r.status_code}, body={preview}")

        payload = _safe_json(r)
        if isinstance(payload, dict) and payload.get("event") == "complete":
            result = payload["data"][0]
            print("ok:", result.get("ok"))
            print("status_html:", result.get("status_html"))
            print("log:", result.get("log"))
            return

        sse_result = _extract_result_from_sse(r.text or "")
        if isinstance(sse_result, dict):
            print("ok:", sse_result.get("ok"))
            print("status_html:", sse_result.get("status_html"))
            print("log:", sse_result.get("log"))
            return

        time.sleep(1.0)


if __name__ == "__main__":
    main()