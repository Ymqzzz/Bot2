from __future__ import annotations

from dataclasses import dataclass
import time

from app.config.settings import BotSettings
from app.data.quality import validate_bars_quality
from app.config.validation import validate_settings
from app.features.price_features import compute_price_features
from app.governance.decision_graph import DecisionGraph
from app.governance.kill_switch import KillSwitch
from app.governance.policy_engine import policy_check
from app.models.calibration import ScoreCalibrator
from app.models.ensemble import choose_best_candidate
from app.intelligence.orchestrator import IntelligenceOrchestrator
from app.monitoring.audit import AuditSink
from app.monitoring.events import EventBus
from app.monitoring.repository import create_event_repository
from app.risk.governors import GovernorState, RiskGovernor
from app.risk.portfolio_adapter import PortfolioContext
from app.risk.sizing import PositionSizer
from app.risk.tail_risk import dislocation_score
from app.strategy.registry import StrategyRegistry
from app.ml.action_space import MetaAction
from app.ml.config import DEFAULT_ML_CONFIG
from app.ml.inference_service import InferenceService
from app.ml.pair_selector import PairSelectionModel
from app.ml.replay_store import ReplayStore
from app.ml.rl_modes import RLMode
from app.ml.state_builder import NormalizationStats, StateBuilder
from app.strategy.plugins.breakout_plugin import BreakoutPlugin
from app.strategy.plugins.mean_reversion_plugin import MeanReversionPlugin
from app.strategy.plugins.momentum_pulse_plugin import MomentumPulsePlugin
from app.strategy.plugins.pullback_reclaim_plugin import PullbackReclaimPlugin
from app.strategy.plugins.trend_plugin import TrendPlugin


@dataclass
class BrokerContext:
    nav: float
    open_positions: list[dict]
    corr_matrix: dict
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    equity_now: float = 0.0


class UpgradedBot:
    def __init__(self, settings: BotSettings | None = None):
        self.settings = settings or BotSettings.from_env()
        validate_settings(self.settings)
        self.registry = StrategyRegistry()
        self.registry.register(TrendPlugin())
        self.registry.register(MeanReversionPlugin())
        self.registry.register(BreakoutPlugin())
        self.registry.register(MomentumPulsePlugin())
        self.registry.register(PullbackReclaimPlugin())
        event_repo = create_event_repository(self.settings.monitoring_events_db_url)
        self.events = EventBus(repository=event_repo, cache_size=self.settings.monitoring_cache_size)
        self.audit = AuditSink()
        self.decision_graph = DecisionGraph(self.events, self.audit)
        self.kill_switch = KillSwitch()
        self.risk_governor = RiskGovernor(max_trades=50)
        self.calibrator = ScoreCalibrator()
        self.intelligence = IntelligenceOrchestrator()
        self.sizer = PositionSizer()
        self.gov_state = GovernorState()
        self._last_trade_ts = 0.0
        self.ml_config = DEFAULT_ML_CONFIG
        self.state_builder = StateBuilder(NormalizationStats(version="v1", mean={}, std={}))
        self.inference = InferenceService(self.ml_config, ReplayStore(self.ml_config.replay_store_path))
        self.pair_selector = PairSelectionModel()

    def _refresh_governor_state(self, broker_ctx: BrokerContext) -> dict[str, float]:
        state = self.gov_state
        state.realized_pnl = broker_ctx.realized_pnl
        state.unrealized_pnl = broker_ctx.unrealized_pnl
        state.equity_now = broker_ctx.equity_now if broker_ctx.equity_now > 0 else broker_ctx.nav
        if state.equity_peak <= 0:
            state.equity_peak = state.equity_now
        else:
            state.equity_peak = max(state.equity_peak, state.equity_now)
        if state.equity_peak > 0:
            state.intraday_drawdown_pct = max(0.0, (state.equity_peak - state.equity_now) / state.equity_peak)
        else:
            state.intraday_drawdown_pct = 0.0
        state.loss_streak = state.loss_streak + 1 if state.daily_pnl < 0 else 0
        return {
            "realized_pnl": state.realized_pnl,
            "unrealized_pnl": state.unrealized_pnl,
            "daily_pnl": state.daily_pnl,
            "equity_now": state.equity_now,
            "equity_peak": state.equity_peak,
            "current_drawdown_pct": state.intraday_drawdown_pct,
            "loss_streak": state.loss_streak,
            "trades_today": state.trades_today,
        }



    def _build_rl_state(self, instrument: str, feats: dict, spread_pctile: float, broker_ctx: BrokerContext, near_event: bool) -> dict:
        market_state = {
            "ret_1": float(feats.get("ret_1", 0.0)),
            "ret_3": float(feats.get("ret_3", 0.0)),
            "ret_12": float(feats.get("ret_12", 0.0)),
            "realized_vol_20": float(feats.get("realized_vol", 0.0)),
            "atr_norm": float(feats.get("atr", 0.0)),
            "trend_slope_20": float(feats.get("trend_slope", 0.0)),
            "mom_10": float(feats.get("momentum", 0.0)),
            "vwap_distance": float(feats.get("vwap_distance", 0.0)),
            "daily_range_pos": float(feats.get("daily_range_pos", 0.0)),
            "prev_day_hilo_proximity": float(feats.get("prev_day_hilo_proximity", 0.0)),
            "liquidity_sweep_flag": float(feats.get("liquidity_sweep", 0.0)),
            "bos_flag": float(feats.get("bos", 0.0)),
            "trend_regime_score": float(feats.get("trend_regime", 0.0)),
            "chop_regime_score": float(feats.get("chop_regime", 0.0)),
        }
        signal_state = {
            "confluence_score": float(feats.get("confluence", 0.0)),
            "buy_score": float(feats.get("buy_score", 0.0)),
            "sell_score": float(feats.get("sell_score", 0.0)),
            "neutral_score": float(feats.get("neutral_score", 0.0)),
            "confidence_score": float(feats.get("confidence", 0.0)),
            "strategy_agreement_count": float(feats.get("strategy_agreement", 0.0)),
            "strategy_disagreement_count": float(feats.get("strategy_disagreement", 0.0)),
            "signal_streak": float(feats.get("signal_streak", 0.0)),
            "instrument_recent_perf": float(feats.get("instrument_recent_perf", 0.0)),
            "setup_recent_perf": float(feats.get("setup_recent_perf", 0.0)),
        }
        risk_state = {
            "open_positions": float(len(broker_ctx.open_positions)),
            "open_risk": float(abs(broker_ctx.unrealized_pnl)),
            "unrealized_pnl": float(broker_ctx.unrealized_pnl),
            "daily_drawdown": float(self.gov_state.intraday_drawdown_pct),
            "weekly_drawdown": float(self.gov_state.intraday_drawdown_pct),
            "trade_count_today": float(self.gov_state.trades_today),
            "loss_streak": float(self.gov_state.loss_streak),
            "risk_budget_remaining": float(max(0.0, self.settings.risk_budget_daily - self.gov_state.intraday_drawdown_pct)),
            "correlation_exposure": 0.0,
            "margin_utilization": 0.0,
            "time_since_last_trade": float(max(0.0, time.time() - self._last_trade_ts)),
        }
        execution_state = {
            "spread": spread_pctile / 100.0,
            "normalized_spread": spread_pctile / max(self.settings.max_spread_pctile, 1.0),
            "slippage_estimate": spread_pctile / 1000.0,
            "latency_ms": 0.0,
            "volatility_burst_flag": float(feats.get("volatility_burst", 0.0)),
        }
        context_state = {
            "session_id": float(time.gmtime().tm_hour // 8),
            "weekday": float(time.gmtime().tm_wday),
            "hour_bucket": float(time.gmtime().tm_hour),
            "macro_event_proximity": 1.0 if near_event else 0.0,
            "news_blackout_flag": 1.0 if near_event else 0.0,
            "weekend_liquidity_flag": 1.0 if time.gmtime().tm_wday >= 5 else 0.0,
            "regime_cluster_id": 0.0,
        }
        return self.state_builder.build(market_state, signal_state, risk_state, execution_state, context_state)

    def _regime(self, bars: list[dict]) -> str:
        d = dislocation_score(bars, 50.0)
        if d > 1.6:
            return "stress"
        if d < 0.6:
            return "calm"
        return "normal"

    def build_candidates(self, instrument: str, bars: list[dict]) -> tuple[list, dict]:
        feats = compute_price_features(bars)
        return self.registry.generate_candidates(instrument, bars, feats), feats

    def run_cycle(self, market_data, broker_ctx: BrokerContext) -> list[dict]:
        active, reason = self.kill_switch.status()
        if active:
            trace = self.events.new_trace()
            self.events.emit("signal_rejected", trace, {"reason": f"kill_switch:{reason}"})
            return []

        state_snapshot = self._refresh_governor_state(broker_ctx)
        trace = self.events.new_trace()
        self.events.emit("risk_state_updated", trace, state_snapshot)

        ok, why, metrics = self.risk_governor.check(self.gov_state, nav=broker_ctx.nav)
        if not ok:
            block_payload = {
                "reason": why,
                "current_drawdown_pct": metrics["current_drawdown_pct"],
                "loss_budget_usage_pct": metrics["loss_budget_usage_pct"],
                "loss_budget": metrics["loss_budget"],
                "loss_used": metrics["loss_used"],
            }
            self.events.emit("risk_blocked", trace, block_payload)
            return []

        decisions = []
        pair_rank_inputs: list[tuple[int, float]] = []
        for instrument in self.settings.instruments:
            bars = market_data.get_recent_bars(instrument, self.settings.granularity, count=150)
            if len(bars) < 40:
                continue
            spread_pctile = market_data.get_spread_pctile(instrument)
            quality = validate_bars_quality(instrument=instrument, bars=bars, spread_pctile=spread_pctile)
            trace = self.events.new_trace()
            if quality.status == "blocked":
                self.events.emit(
                    "data_quality_block",
                    trace,
                    {
                        "instrument": instrument,
                        "failing_rules": quality.failing_rules,
                        "reason_codes": quality.reason_codes,
                    },
                )
                continue
            if quality.status == "degraded":
                self.events.emit(
                    "data_quality_degraded",
                    trace,
                    {
                        "instrument": instrument,
                        "failing_rules": quality.failing_rules,
                        "reason_codes": quality.reason_codes,
                    },
                )
            else:
                self.events.emit("data_quality_pass", trace, {"instrument": instrument, "failing_rules": []})

            liq = market_data.get_liquidity_factor(instrument)
            near_event = market_data.has_near_event(instrument)
            disloc = dislocation_score(bars, spread_pctile)
            pass_policy, reason = policy_check(
                spread_pctile=spread_pctile,
                dislocation=disloc,
                near_event=near_event,
                max_spread_pctile=self.settings.max_spread_pctile,
            )
            if not pass_policy:
                trace = self.events.new_trace()
                self.events.emit("signal_rejected", trace, {"instrument": instrument, "reason": reason, "dislocation": disloc})
                continue

            cands, feats = self.build_candidates(instrument, bars)
            regime = self._regime(bars)
            pwin_map = {i: self.calibrator.calibrate(c.score, regime=regime) for i, c in enumerate(cands)}
            intel_by_idx = {}
            quality_modifiers: dict[int, float] = {}
            for idx, cand in enumerate(cands):
                intel = self.intelligence.build_snapshot(
                    instrument=instrument,
                    bars=bars,
                    features={**feats, "spread_percentile": spread_pctile, "atr_percentile": float(feats.get("atr", 0.5))},
                    context={
                        "trace_id": trace,
                        "near_event": near_event,
                        "minutes_to_event": 30.0 if near_event else 9999.0,
                        "minutes_since_event": 9999.0,
                        "event_severity": 0.8 if near_event else 0.0,
                        "event_relevance": 0.8 if near_event else 0.0,
                        "slippage_percentile": 0.25,
                        "execution_cost": spread_pctile / 100.0,
                        "strategy_performance": {},
                        "cross_asset": {},
                        "analog_history": [],
                    },
                    candidate_strategy=cand.strategy,
                    raw_confidence=pwin_map[idx],
                )
                intel_by_idx[idx] = intel
                quality_modifiers[idx] = max(0.25, intel.trade_quality.trade_quality_score * intel.uncertainty.size_penalty_multiplier)
            best = choose_best_candidate(cands, pwin_map, intelligence_modifiers=quality_modifiers)
            if best is None:
                continue

            intel_snapshot = self.intelligence.build_snapshot(
                instrument=instrument,
                bars=bars,
                features={**feats, "spread_percentile": spread_pctile, "atr_percentile": float(feats.get("atr", 0.5))},
                context={
                    "trace_id": trace,
                    "near_event": near_event,
                    "minutes_to_event": 30.0 if near_event else 9999.0,
                    "minutes_since_event": 9999.0,
                    "event_severity": 0.8 if near_event else 0.0,
                    "event_relevance": 0.8 if near_event else 0.0,
                    "slippage_percentile": 0.25,
                    "execution_cost": spread_pctile / 100.0,
                    "strategy_performance": {},
                    "cross_asset": {},
                    "analog_history": [],
                },
                candidate_strategy=best.strategy,
                raw_confidence=best.score,
            )
            refined_score = intel_snapshot.calibration.calibrated_confidence
            refined_score *= (0.75 + 0.25 * intel_snapshot.trade_quality.quality_score)
            refined_score *= (1.0 - 0.25 * intel_snapshot.uncertainty.ranking_penalty)
            best.score = max(0.0, min(1.0, refined_score))
            best_idx = cands.index(best)
            intel_snapshot = intel_by_idx[best_idx]
            best.score = intel_snapshot.calibration.calibrated_confidence
            ml_payload = {
                "confidence": best.score,
                "confluence": float(feats.get("confluence", 0.0)),
                "setup_recent_perf": float(feats.get("setup_recent_perf", 0.0)),
                "instrument_recent_perf": float(feats.get("instrument_recent_perf", 0.0)),
                "spread_norm": spread_pctile / max(self.settings.max_spread_pctile, 1.0),
                "volatility_burst": float(feats.get("volatility_burst", 0.0)),
                "previous_entry_quality": float(intel_snapshot.trade_quality.trade_quality_score),
            }
            ml_signal = self.pair_selector.score(instrument, ml_payload)
            best.score = max(0.0, min(1.0, best.score * (0.65 + 0.35 * ml_signal.trade_likelihood)))

            now = time.time()
            if now - self._last_trade_ts < self.settings.min_trade_interval_sec:
                continue
            sizing = self.sizer.compute_units(
                side=best.side,
                nav=broker_ctx.nav,
                entry_price=best.entry_price,
                stop_loss=best.stop_loss,
                atr=float(feats.get("atr", 0.0)),
                dislocation=disloc,
                spread_pctile=spread_pctile,
                confidence=best.score,
                open_positions=broker_ctx.open_positions,
                daily_risk_pct=self.settings.risk_budget_daily,
                cluster_risk_pct=self.settings.cluster_risk_cap,
                quality_multiplier=intel_snapshot.trade_quality.size_multiplier_hint,
                uncertainty_multiplier=intel_snapshot.uncertainty.size_penalty_multiplier,
                strategy_health_multiplier=intel_snapshot.strategy_health.throttle_multipliers.get(best.strategy, 1.0),
                strategy_multiplier=intel_snapshot.strategy_health.throttle_multipliers.get(best.strategy, 1.0),
            )
            if sizing.signed_units == 0:
                trace = self.events.new_trace()
                self.events.emit("signal_rejected", trace, {"instrument": instrument, "reason": "size_zero", "sizing": sizing.to_dict()})
                continue
            trace = self.events.new_trace()
            decision = self.decision_graph.evaluate(
                trace_id=trace,
                candidate=best,
                spread_pctile=spread_pctile,
                liquidity_factor=liq,
                has_near_event=near_event,
                signed_units=sizing.signed_units,
                sizing_diagnostics=sizing.to_dict(),
                portfolio_ctx=PortfolioContext(
                    open_positions=broker_ctx.open_positions,
                    nav=broker_ctx.nav,
                    corr_matrix=broker_ctx.corr_matrix,
                ),
                min_score=max(0.05, self.settings.min_signal_score * (1.2 - 0.4 * ml_signal.trade_likelihood)),
                max_spread_pctile=self.settings.max_spread_pctile,
                daily_risk_pct=self.settings.risk_budget_daily,
                cluster_risk_pct=self.settings.cluster_risk_cap,
            )
            rl_state = self._build_rl_state(instrument, feats, spread_pctile, broker_ctx, near_event)
            rl_decision = self.inference.infer(
                model=self.calibrator,
                state=rl_state,
                mode=RLMode(self.ml_config.mode),
                has_candidate=True,
                in_position=any(p.get("instrument") == instrument for p in broker_ctx.open_positions),
                risk_deterioration=self.gov_state.intraday_drawdown_pct > self.settings.risk_budget_daily,
                baseline_action=int(MetaAction.ALLOW_AS_IS),
                ood_score=min(1.0, rl_state.missing_mask.mean()),
            )
            decision["rl_overlay"] = {
                "action": rl_decision.action,
                "confidence": rl_decision.gated.confidence,
                "entropy": rl_decision.gated.entropy,
                "gated_reason": rl_decision.gated.reason,
                "latency_ms": rl_decision.latency_ms,
            }
            decision["regime"] = regime
            decision["market_intelligence"] = intel_snapshot.to_dict()
            decision["ml_pair_selection"] = {
                "trade_likelihood": ml_signal.trade_likelihood,
                "pair_score": ml_signal.pair_score,
                "expected_result": ml_signal.expected_result,
                "estimated_sharpe_improvement": ml_signal.sharpe_improvement,
                "baseline_sharpe": self.pair_selector.baseline_sharpe(),
            }
            decision["dislocation"] = disloc
            decision["data_quality_status"] = quality.status
            decision["data_quality_reason_codes"] = quality.reason_codes
            realized_proxy = (
                0.5 * float(feats.get("instrument_recent_perf", 0.0))
                + 0.3 * float(feats.get("setup_recent_perf", 0.0))
                + 0.2 * float(feats.get("confluence", 0.0))
            )
            self.pair_selector.learn(instrument, ml_payload, realized_result=realized_proxy)
            pair_rank_inputs.append((len(decisions), ml_signal.pair_score))
            if decision.get("approved"):
                self._last_trade_ts = now
                self.gov_state.trades_today += 1
            self.audit.append(
                {
                    "type": "market_intelligence",
                    "trace_id": trace,
                    "instrument": instrument,
                    "snapshot": intel_snapshot.to_dict(),
                }
            )
            decisions.append(decision)
        ranked_positions = {idx: rank + 1 for rank, (idx, _) in enumerate(sorted(pair_rank_inputs, key=lambda x: x[1], reverse=True))}
        for idx, decision in enumerate(decisions):
            rank = ranked_positions.get(idx)
            if rank is None:
                continue
            decision.setdefault("ml_pair_selection", {})["pair_rank"] = rank
        return decisions
