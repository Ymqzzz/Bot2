from __future__ import annotations


def build_feature_overlap_matrix(feature_sets: dict[str, set[str]]) -> dict[tuple[str, str], float]:
    keys = list(feature_sets)
    out: dict[tuple[str, str], float] = {}
    for i, a in enumerate(keys):
        for b in keys[i + 1 :]:
            sa = feature_sets[a]
            sb = feature_sets[b]
            if not sa and not sb:
                overlap = 0.0
            else:
                overlap = len(sa & sb) / max(1, len(sa | sb))
            out[(a, b)] = overlap
    return out
