from __future__ import annotations


def purged_time_splits(size: int, folds: int, purge: int) -> list[tuple[range, range]]:
    if folds < 2:
        raise ValueError("folds must be >= 2")
    chunk = max(1, size // folds)
    out: list[tuple[range, range]] = []
    for i in range(folds):
        test_start = i * chunk
        test_end = size if i == folds - 1 else (i + 1) * chunk
        train = [x for x in range(size) if x < test_start - purge or x >= test_end + purge]
        out.append((range(len(train)), range(test_start, test_end)))
    return out
