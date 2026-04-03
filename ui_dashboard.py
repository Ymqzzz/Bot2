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
    total_cpu = sum(process["cpu_percent"] for process in processes)
    total_memory_mb = sum(process["memory_mb"] for process in processes)
    heavy_process = processes[0] if processes else None

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
        :root {{
            color-scheme: dark;
            --bg: #0b1220;
            --bg-accent: radial-gradient(circle at top right, rgba(59, 130, 246, 0.2), transparent 36%);
            --card: #111827;
            --card-border: #1f2937;
            --text: #e2e8f0;
            --muted: #94a3b8;
            --primary: #93c5fd;
            --secondary: #bfdbfe;
        }}
        body {{ font-family: Inter, Arial, sans-serif; margin: 0; padding: 1rem 1.2rem 2rem; background: var(--bg); background-image: var(--bg-accent); color: var(--text); }}
        .header {{ display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: .8rem; margin-bottom: 1rem; }}
        .header-right {{ text-align: right; }}
        .pill {{ display: inline-block; background: #1e293b; border: 1px solid #334155; border-radius: 999px; padding: .22rem .6rem; font-size: .8rem; color: var(--secondary); }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: .8rem; margin-bottom: 1rem; }}
        .stat {{ background: linear-gradient(180deg, #111827 0%, #0f172a 100%); border: 1px solid var(--card-border); border-radius: 10px; padding: .75rem .85rem; }}
        .stat .label {{ color: var(--muted); font-size: .8rem; margin-bottom: .2rem; }}
        .stat .value {{ font-size: 1.1rem; font-weight: 600; letter-spacing: .01em; color: #f8fafc; }}
        .grid {{ display: grid; grid-template-columns: repeat(12, 1fr); gap: 1rem; }}
        .card {{ background: var(--card); border: 1px solid var(--card-border); border-radius: 12px; padding: 1rem; box-shadow: 0 10px 24px rgba(15, 23, 42, .3); }}
        .full {{ grid-column: span 12; }}
        h1, h2 {{ margin: 0 0 .7rem 0; }}
        h1 {{ font-size: 1.45rem; }}
        a {{ color: var(--primary); text-underline-offset: 2px; }}
        table {{ width: 100%; border-collapse: collapse; font-size: .9rem; }}
        th, td {{ border-bottom: 1px solid var(--card-border); padding: .5rem; text-align: left; vertical-align: top; }}
        th {{ color: var(--primary); position: sticky; top: 0; background: #0f172a; z-index: 1; }}
        tr:nth-child(even) td {{ background: rgba(30, 41, 59, .25); }}
        code {{ color: var(--secondary); font-size: .82rem; }}
        pre {{ max-height: 260px; overflow: auto; background: #020617; border: 1px solid var(--card-border); padding: .7rem; border-radius: 8px; white-space: pre-wrap; }}
        details.log-card {{ margin: .5rem 0 .7rem 0; }}
        summary {{ cursor: pointer; color: var(--primary); font-weight: 600; }}
        .muted {{ color: var(--muted); font-size: .85rem; margin-top: .4rem; }}
        .table-wrap {{ max-height: 380px; overflow: auto; border: 1px solid var(--card-border); border-radius: 8px; }}
        .routes {{ margin-top: .5rem; line-height: 1.5; }}
    </style>
</head>
<body>
    <header class=\"header\">
        <div>
            <h1>Runtime Ops Dashboard</h1>
            <div class=\"muted\">Live view for processes and logs.</div>
        </div>
        <div class=\"header-right\">
            <span class=\"pill\">Auto refresh: {AUTO_REFRESH_SECONDS}s</span>
            <div class=\"muted routes\">Paths: <a href=\"/\">/</a>, <a href=\"/dashboard\">/dashboard</a>, <a href=\"/ui\">/ui</a>, <a href=\"/ui/dashboard\">/ui/dashboard</a>{f', base path prefix: {html.escape(UI_BASE_PATH)}' if UI_BASE_PATH else ''}</div>
        </div>
    </header>

    <section class=\"stats\">
        <article class=\"stat\"><div class=\"label\">Processes</div><div class=\"value\">{len(processes)}</div></article>
        <article class=\"stat\"><div class=\"label\">Log Files</div><div class=\"value\">{len(logs)}</div></article>
        <article class=\"stat\"><div class=\"label\">Combined CPU%</div><div class=\"value\">{total_cpu:.1f}</div></article>
        <article class=\"stat\"><div class=\"label\">Combined Memory MB</div><div class=\"value\">{total_memory_mb:.2f}</div></article>
        <article class=\"stat\"><div class=\"label\">Top Process</div><div class=\"value\">{html.escape(heavy_process['name']) if heavy_process else 'N/A'}</div></article>
    </section>

    <div class=\"grid\">
        <section class=\"card full\">
            <h2>Processes ({len(processes)})</h2>
            <div class=\"table-wrap\">
                <table>
                    <thead><tr><th>PID</th><th>Name</th><th>Status</th><th>CPU%</th><th>Memory MB</th><th>Command</th></tr></thead>
                    <tbody>{process_rows}</tbody>
                </table>
            </div>
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
    registered_paths: set[str] = set()

    for base in base_paths:
        for route in dashboards:
            path = f"{base}{route}" if route != "/" else (base or "/")
            if path in registered_paths:
                continue
            registered_paths.add(path)
            endpoint = f"dashboard_{len(registered_paths)}"
            app.add_url_rule(path, endpoint=endpoint, view_func=dashboard)

        health_path = f"{base}/health" if base else "/health"
        if health_path in registered_paths:
            continue
        registered_paths.add(health_path)
        endpoint = f"health_{len(registered_paths)}"
        app.add_url_rule(health_path, endpoint=endpoint, view_func=health)


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
