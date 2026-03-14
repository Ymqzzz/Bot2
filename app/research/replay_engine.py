from __future__ import annotations

from dataclasses import dataclass

from app.runtime.upgraded_bot import UpgradedBot, BrokerContext


@dataclass
class ReplayResult:
    cycles: int
    approved: int
    blocked: int


class ReplayEngine:
    def run(self, bot: UpgradedBot, market_data, broker_ctx: BrokerContext, cycles: int = 5) -> ReplayResult:
        approved = 0
        blocked = 0
        for _ in range(cycles):
            decisions = bot.run_cycle(market_data, broker_ctx)
            approved += sum(1 for d in decisions if d.get("approved"))
            blocked += sum(1 for d in decisions if not d.get("approved"))
        return ReplayResult(cycles=cycles, approved=approved, blocked=blocked)
