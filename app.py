from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from flask import Flask, jsonify, request

from main import build_runtime


def _coerce_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _coerce_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def create_app() -> Flask:
    app = Flask(__name__)
    runtime = build_runtime()

    @app.get("/healthz")
    def healthz() -> Any:
        return jsonify({"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()})

    @app.post("/runtime/cycle")
    def runtime_cycle() -> Any:
        payload = request.get_json(silent=True) or {}
        result = runtime.run_cycle(
            instruments=_coerce_list(payload.get("instruments")),
            market_data=_coerce_dict(payload.get("market_data")),
            bars=_coerce_dict(payload.get("bars")),
            open_positions=_coerce_list(payload.get("open_positions")),
            candidate_pool=_coerce_list(payload.get("candidate_pool")),
            context=_coerce_dict(payload.get("context")),
        )
        return jsonify(result)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
