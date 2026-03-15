from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from flask import Flask, jsonify, request

from main import build_runtime


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
            instruments=list(payload.get("instruments", [])),
            market_data=dict(payload.get("market_data", {})),
            bars=dict(payload.get("bars", {})),
            open_positions=list(payload.get("open_positions", [])),
            candidate_pool=list(payload.get("candidate_pool", [])),
            context=dict(payload.get("context", {})),
        )
        return jsonify(result)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
