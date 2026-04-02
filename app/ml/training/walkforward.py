from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WindowSplit:
    train: tuple[int, int]
    validate: tuple[int, int]
    test: tuple[int, int]


def build_walkforward_splits(total_rows: int, train_size: int, validate_size: int, test_size: int, step: int) -> list[WindowSplit]:
    if min(train_size, validate_size, test_size, step) <= 0:
        raise ValueError("all sizes must be positive")
    splits: list[WindowSplit] = []
    anchor = 0
    while anchor + train_size + validate_size + test_size <= total_rows:
        splits.append(
            WindowSplit(
                train=(anchor, anchor + train_size),
                validate=(anchor + train_size, anchor + train_size + validate_size),
                test=(anchor + train_size + validate_size, anchor + train_size + validate_size + test_size),
            )
        )
        anchor += step
    return splits
