from __future__ import annotations

from app.intelligence.base import clamp


class CrowdingPenaltyModel:
    def penalty(self, *, crowding_score: float, post_win_streak: int) -> float:
        streak_term = clamp(post_win_streak / 6.0)
        return clamp(crowding_score * 0.75 + streak_term * 0.25)
