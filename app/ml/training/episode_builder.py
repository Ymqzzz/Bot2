from __future__ import annotations

from app.ml.training.dataset_builder import DatasetRow


def build_episodes(rows: list[DatasetRow], episode_size: int) -> list[list[DatasetRow]]:
    if episode_size <= 0:
        raise ValueError("episode_size must be positive")
    episodes: list[list[DatasetRow]] = []
    for idx in range(0, len(rows), episode_size):
        episodes.append(rows[idx : idx + episode_size])
    return episodes
