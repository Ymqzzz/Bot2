from __future__ import annotations


def apply_embargo(indices: list[int], embargo: int, max_index: int) -> list[int]:
    banned = set()
    for idx in indices:
        for i in range(max(0, idx - embargo), min(max_index, idx + embargo + 1)):
            banned.add(i)
    return [i for i in range(max_index) if i not in banned]
