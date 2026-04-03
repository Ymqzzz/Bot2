from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from statistics import mean

from app.intelligence.institutional.schemas import (
    FailureCluster,
    MarketMemoryAssessment,
    MemoryQuery,
    SetupRecord,
    SimilarSetup,
)


@dataclass(frozen=True)
class SimilarityWeights:
    setup: float = 0.22
    regime: float = 0.15
    session: float = 0.10
    instrument: float = 0.12
    direction: float = 0.12
    compression: float = 0.12
    volatility: float = 0.07
    post_news: float = 0.05
    microstructure: float = 0.05


class SetupSimilarityIndex:
    def __init__(self, *, weights: SimilarityWeights | None = None) -> None:
        self.weights = weights or SimilarityWeights()

    def score(self, query: MemoryQuery, record: SetupRecord) -> float:
        w = self.weights
        score = 0.0
        score += w.setup if query.setup_type == record.setup_type else 0.0
        score += w.regime if query.regime == record.regime else 0.0
        score += w.session if query.session == record.session else 0.0
        score += w.instrument if query.instrument == record.instrument else 0.0
        score += w.direction if query.direction == record.direction else 0.0
        score += max(0.0, w.compression - abs(query.compression_score - record.compression_score) * 0.5)
        score += w.volatility if query.volatility_state == record.volatility_state else 0.0
        score += w.post_news if query.post_news_state == record.post_news_state else 0.0
        score += w.microstructure if query.microstructure_tag == record.microstructure_tag else 0.0
        return min(1.0, max(0.0, score))


class HistoricalPatternStore:
    def __init__(self) -> None:
        self._records: dict[str, SetupRecord] = {}

    def add(self, record: SetupRecord) -> None:
        self._records[record.record_id] = record

    def all(self) -> list[SetupRecord]:
        return list(self._records.values())

    def by_setup(self, setup_type: str) -> list[SetupRecord]:
        return [r for r in self._records.values() if r.setup_type == setup_type]


class ContextualFailureClusters:
    def build(self, records: list[tuple[float, SetupRecord]]) -> list[FailureCluster]:
        grouped: dict[tuple[str, str, str], list[tuple[float, SetupRecord]]] = defaultdict(list)
        for sim, rec in records:
            if rec.pnl_r < 0:
                grouped[(rec.regime, rec.session, rec.microstructure_tag)].append((sim, rec))

        clusters: list[FailureCluster] = []
        for idx, ((regime, session, micro), items) in enumerate(grouped.items(), start=1):
            weighted_sum = sum(s for s, _ in items)
            weighted_losses = sum(s * abs(r.pnl_r) for s, r in items)
            clusters.append(
                FailureCluster(
                    cluster_id=f"fc_{idx}",
                    label=f"{regime}:{session}:{micro}",
                    frequency=min(1.0, len(items) / max(1, len(records))),
                    avg_loss_r=weighted_losses / max(weighted_sum, 1e-9),
                    dominant_regime=regime,
                    dominant_session=session,
                )
            )
        clusters.sort(key=lambda c: (c.frequency, c.avg_loss_r), reverse=True)
        return clusters[:5]


class MarketMemoryScorer:
    def score(self, records: list[tuple[float, SetupRecord]], top_matches: list[SimilarSetup], clusters: list[FailureCluster]) -> MarketMemoryAssessment:
        if not records:
            return MarketMemoryAssessment(
                samples=0,
                weighted_win_rate=0.5,
                weighted_expectancy_r=0.0,
                weighted_stop_out_rate=0.5,
                weighted_mfe_r=0.0,
                weighted_mae_r=0.0,
                mean_holding_bars=0.0,
                fragility_score=0.55,
                confidence=0.0,
                failure_clusters=[],
                top_matches=[],
            )

        weighted_total = sum(w for w, _ in records)
        win = sum(w for w, r in records if r.pnl_r > 0) / max(weighted_total, 1e-9)
        expectancy = sum(w * r.pnl_r for w, r in records) / max(weighted_total, 1e-9)
        stop_rate = sum(w for w, r in records if r.stop_out) / max(weighted_total, 1e-9)
        mfe = sum(w * r.mfe_r for w, r in records) / max(weighted_total, 1e-9)
        mae = sum(w * r.mae_r for w, r in records) / max(weighted_total, 1e-9)
        holding = sum(w * r.holding_bars for w, r in records) / max(weighted_total, 1e-9)

        cluster_penalty = mean([c.frequency * min(1.0, c.avg_loss_r / 2.5) for c in clusters]) if clusters else 0.0
        fragility = min(
            1.0,
            max(
                0.0,
                stop_rate * 0.45
                + max(0.0, 0.5 - win) * 0.40
                + max(0.0, -expectancy) * 0.35
                + max(0.0, mae - mfe) * 0.08
                + cluster_penalty * 0.35,
            ),
        )
        confidence = min(1.0, len(records) / 40.0)

        return MarketMemoryAssessment(
            samples=len(records),
            weighted_win_rate=win,
            weighted_expectancy_r=expectancy,
            weighted_stop_out_rate=stop_rate,
            weighted_mfe_r=mfe,
            weighted_mae_r=mae,
            mean_holding_bars=holding,
            fragility_score=fragility,
            confidence=confidence,
            failure_clusters=clusters,
            top_matches=top_matches,
        )


class ContextRetrieval:
    def __init__(self, similarity_index: SetupSimilarityIndex) -> None:
        self._sim = similarity_index

    def retrieve(self, query: MemoryQuery, records: list[SetupRecord], *, min_similarity: float = 0.25, top_n: int = 60) -> list[tuple[float, SetupRecord]]:
        scored: list[tuple[float, SetupRecord]] = []
        for rec in records:
            score = self._sim.score(query, rec)
            if score >= min_similarity:
                scored.append((score, rec))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:top_n]


class MarketMemoryEngine:
    def __init__(self) -> None:
        self.store = HistoricalPatternStore()
        self.similarity = SetupSimilarityIndex()
        self.context = ContextRetrieval(self.similarity)
        self.clusters = ContextualFailureClusters()
        self.scorer = MarketMemoryScorer()

    def ingest(self, record: SetupRecord) -> None:
        self.store.add(record)

    def assess(self, query: MemoryQuery) -> MarketMemoryAssessment:
        retrieved = self.context.retrieve(query, self.store.all())
        top_matches = [
            SimilarSetup(
                record_id=r.record_id,
                similarity=sim,
                pnl_r=r.pnl_r,
                stop_out=r.stop_out,
                holding_bars=r.holding_bars,
                regime=r.regime,
                session=r.session,
            )
            for sim, r in retrieved[:12]
        ]
        clusters = self.clusters.build(retrieved)
        return self.scorer.score(retrieved, top_matches, clusters)


__all__ = [
    "ContextRetrieval",
    "ContextualFailureClusters",
    "HistoricalPatternStore",
    "MarketMemoryEngine",
    "MarketMemoryScorer",
    "SetupSimilarityIndex",
    "SimilarityWeights",
]
