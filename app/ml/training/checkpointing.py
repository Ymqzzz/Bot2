from __future__ import annotations

from pathlib import Path
import pickle


def save_checkpoint(model: object, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        pickle.dump(model, fh)
