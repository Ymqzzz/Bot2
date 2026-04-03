from __future__ import annotations


def allocate_clusters(overlap: dict[tuple[str, str], float], threshold: float = 0.65) -> list[set[str]]:
    nodes = sorted({n for pair in overlap for n in pair})
    if not nodes:
        return []

    parent = {n: n for n in nodes}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for (a, b), ov in overlap.items():
        if ov >= threshold:
            union(a, b)

    clusters: dict[str, set[str]] = {}
    for n in nodes:
        clusters.setdefault(find(n), set()).add(n)
    return list(clusters.values())
