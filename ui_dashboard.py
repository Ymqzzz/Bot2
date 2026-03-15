from __future__ import annotations

import html
import os
from pathlib import Path
from typing import Any

import psutil
from dotenv import load_dotenv
from flask import Flask

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _normalized_base_path() -> str:
    raw = (os.getenv("UI_BASE_PATH", "") or "").strip()
    if not raw or raw == "/":
        return ""
    raw = raw if raw.startswith("/") else f"/{raw}"
    return raw.rstrip("/")


MAX_LOG_BYTES = _env_int("MAX_LOG_BYTES", 200000)
LOG_LINES = _env_int("LOG_LINES", 200)
AUTO_REFRESH_SECONDS = _env_int("AUTO_REFRESH_SECONDS", 10)
LOG_GLOBS = [
    pattern.strip()
    for pattern in os.getenv("LOG_GLOBS", "*.log,*.jsonl,control_plane_logs/*.jsonl,research_outputs/*.json").split(",")
    if pattern.strip()
]
PROCESS_FILTER = os.getenv("PROCESS_FILTER", "").strip().lower()
UI_BASE_PATH = _normalized_base_path()

app = Flask(__name__)


def _read_log_tail(file_path: Path, max_lines: int = LOG_LINES) -> str:
    try:
        with file_path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            file_size = handle.tell()
            handle.seek(max(0, file_size - MAX_LOG_BYTES))
            data = handle.read().decode("utf-8", errors="replace")
        lines = data.splitlines()
        return "\n".join(lines[-max_lines:])
    except OSError as error:
        return f"Unable to read log file: {error}"


def _collect_logs() -> list[dict[str, Any]]:
    discovered: dict[str, Path] = {}
    for pattern in LOG_GLOBS:
        for path in BASE_DIR.glob(pattern):
            if path.is_file():
                discovered[str(path.relative_to(BASE_DIR))] = path

    logs: list[dict[str, Any]] = []
    for relative_name in sorted(discovered):
        path = discovered[relative_name]
        try:
            size_kb = round(path.stat().st_size / 1024, 2)
        except OSError:
            size_kb = 0.0
        logs.append({"name": relative_name, "size_kb": size_kb, "tail": _read_log_tail(path)})
    return logs


def _collect_processes() -> list[dict[str, Any]]:
    processes: list[dict[str, Any]] = []
    for process in psutil.process_iter(attrs=["pid", "name", "status", "cpu_percent", "memory_info", "cmdline"]):
        try:
            info = process.info
            cmdline = " ".join(info.get("cmdline") or [])
            name = str(info.get("name") or "unknown")
            if PROCESS_FILTER and PROCESS_FILTER not in cmdline.lower() and PROCESS_FILTER not in name.lower():
                continue
            memory_info = info.get("memory_info")
            memory_mb = round((memory_info.rss if memory_info else 0) / (1024 * 1024), 2)
            processes.append(
                {
                    "pid": info.get("pid"),
                    "name": name,
                    "status": info.get("status") or "unknown",
                    "cpu_percent": float(info.get("cpu_percent") or 0.0),
                    "memory_mb": memory_mb,
                    "cmdline": cmdline or "-",
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    processes.sort(key=lambda item: (item["cpu_percent"], item["memory_mb"]), reverse=True)
    return processes


def dashboard() -> str:
    logs = _collect_logs()
    processes = _collect_processes()

    process_rows = "".join(
        f"<tr><td>{p['pid']}</td><td>{html.escape(p['name'])}</td><td>{html.escape(p['status'])}</td><td>{p['cpu_percent']:.1f}</td><td>{p['memory_mb']:.2f}</td><td><code>{html.escape(p['cmdline'])}</code></td></tr>"
        for p in processes
    ) or "<tr><td colspan='6' class='muted'>No running processes found for current filter.</td></tr>"

    log_sections = "".join(
        f"""
        <details class=\"log-card\" open>
            <summary>{html.escape(item['name'])} ({item['size_kb']} KB)</summary>
            <pre>{html.escape(item['tail'])}</pre>
        </details>
        """
        for item in logs
    )

    return f"""
<!doctype html>
<html lang=\"en\">
<head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <meta http-equiv=\"refresh\" content=\"{AUTO_REFRESH_SECONDS}\" />
    <title>Runtime Ops Dashboard</title>
    <style>
        body {{ font-family: Inter, Arial, sans-serif; margin: 0; padding: 1rem 1.2rem; background: #0f172a; color: #e2e8f0; }}
        .grid {{ display: grid; grid-template-columns: repeat(12, 1fr); gap: 1rem; }}
        .card {{ background: #111827; border: 1px solid #1f2937; border-radius: 10px; padding: 1rem; }}
        .full {{ grid-column: span 12; }}
        h1, h2 {{ margin: 0 0 .7rem 0; }}
        a {{ color: #93c5fd; }}
        table {{ width: 100%; border-collapse: collapse; font-size: .9rem; }}
        th, td {{ border-bottom: 1px solid #1f2937; padding: .45rem; text-align: left; vertical-align: top; }}
        th {{ color: #93c5fd; }}
        code {{ color: #bfdbfe; }}
        pre {{ max-height: 260px; overflow: auto; background: #020617; border: 1px solid #1f2937; padding: .7rem; border-radius: 8px; white-space: pre-wrap; }}
        details.log-card {{ margin: .5rem 0 .7rem 0; }}
        summary {{ cursor: pointer; color: #93c5fd; font-weight: 600; }}
        .muted {{ color: #94a3b8; font-size: .85rem; margin-top: .4rem; }}
    </style>
</head>
<body>
    <h1>Runtime Ops Dashboard</h1>
    <div class=\"muted\">Streamlined live view for processes and logs. Auto refresh every {AUTO_REFRESH_SECONDS}s.</div>
    <div class=\"muted\">Paths: <a href=\"/\">/</a>, <a href=\"/dashboard\">/dashboard</a>, <a href=\"/ui\">/ui</a>, <a href=\"/ui/dashboard\">/ui/dashboard</a>{f', base path prefix: {html.escape(UI_BASE_PATH)}' if UI_BASE_PATH else ''}</div>

    <div class=\"grid\">
        <section class=\"card full\">
            <h2>Processes ({len(processes)})</h2>
            <table>
                <thead><tr><th>PID</th><th>Name</th><th>Status</th><th>CPU%</th><th>Memory MB</th><th>Command</th></tr></thead>
                <tbody>{process_rows}</tbody>
            </table>
        </section>

        <section class=\"card full\">
            <h2>Logs ({len(logs)})</h2>
            {log_sections or '<div class="muted">No log files matched LOG_GLOBS yet.</div>'}
        </section>
    </div>
</body>
</html>
"""


def health() -> dict[str, str]:
    return {"status": "ok"}


def _register_aliases() -> None:
    base_paths = ["", UI_BASE_PATH] if UI_BASE_PATH else [""]
    dashboards = ["/", "/dashboard", "/ui", "/ui/dashboard"]
    for base in base_paths:
        for route in dashboards:
            path = f"{base}{route}" if route != "/" else (base or "/")
            app.add_url_rule(path, endpoint=f"dashboard_{path}", view_func=dashboard)

        app.add_url_rule(f"{base}/health" if base else "/health", endpoint=f"health_{base or 'root'}", view_func=health)


_register_aliases()


@app.errorhandler(404)
def not_found(_error):
    links = ["/", "/dashboard", "/ui", "/ui/dashboard", "/health"]
    if UI_BASE_PATH:
        links.extend([
            f"{UI_BASE_PATH}/",
            f"{UI_BASE_PATH}/dashboard",
            f"{UI_BASE_PATH}/ui",
            f"{UI_BASE_PATH}/ui/dashboard",
            f"{UI_BASE_PATH}/health",
        ])
    list_html = "".join(f"<li><a href='{html.escape(path)}'>{html.escape(path)}</a></li>" for path in links)
    return (
        f"<h2>Route not found</h2><p>Try one of these routes:</p><ul>{list_html}</ul>",
        404,
        {"Content-Type": "text/html; charset=utf-8"},
    )


if __name__ == "__main__":
    app.run(
        host=os.getenv("UI_HOST", "0.0.0.0"),
        port=_env_int("UI_PORT", 8000),
        debug=os.getenv("UI_DEBUG", "false").lower() == "true",
    )
