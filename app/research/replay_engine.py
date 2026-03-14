from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from app.runtime.upgraded_bot import UpgradedBot, BrokerContext


@dataclass
class ReplayResult:
    cycles: int
    approved: int
    blocked: int
    approval_rate: float
    block_reasons: dict[str, int]


class ReplayEngine:
    def run(self, bot: UpgradedBot, market_data, broker_ctx: BrokerContext, cycles: int = 5) -> ReplayResult:
        approved = 0
        blocked = 0
        block_reasons: Counter[str] = Counter()

        for _ in range(cycles):
            decisions = bot.run_cycle(market_data, broker_ctx)
            approved += sum(1 for d in decisions if d.get("approved"))
            for d in decisions:
                if d.get("approved"):
                    continue
                blocked += 1
                block_reasons[d.get("reason", "unknown")] += 1

        denom = max(1, approved + blocked)
        return ReplayResult(
            cycles=cycles,
            approved=approved,
            blocked=blocked,
            approval_rate=approved / denom,
            block_reasons=dict(block_reasons),
        )
