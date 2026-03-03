from __future__ import annotations


def lifecycle_actions(meta: dict, progress_r: float, bars_open: int, time_stop_bars: int, min_progress_r: float = 0.5):
    actions = []
    if bars_open >= time_stop_bars and progress_r < min_progress_r:
        actions.append("time_stop_exit")
    if progress_r >= 1.0 and not meta.get("partial_taken"):
        actions.append("take_partial")
        actions.append("move_sl_to_be")
    if progress_r >= 1.5:
        actions.append("trail_stop")
    return actions
