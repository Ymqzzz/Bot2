from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


_APP_SPEC = spec_from_file_location("http_app", Path(__file__).resolve().parents[1] / "app.py")
assert _APP_SPEC and _APP_SPEC.loader
_APP_MODULE = module_from_spec(_APP_SPEC)
_APP_SPEC.loader.exec_module(_APP_MODULE)
create_app = _APP_MODULE.create_app


def test_runtime_cycle_handles_null_collections() -> None:
    flask_app = create_app()
    client = flask_app.test_client()

    response = client.post(
        "/runtime/cycle",
        json={
            "instruments": None,
            "market_data": None,
            "bars": None,
            "open_positions": None,
            "candidate_pool": None,
            "context": None,
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert isinstance(body, dict)
    assert "execution_plan" in body
    assert "persisted_records" in body
