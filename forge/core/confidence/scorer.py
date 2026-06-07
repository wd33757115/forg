"""ConfidenceScorer — v1.1 session confidence for approval gating."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from forge.core.confidence.config import (
    DEFAULT_WEIGHTS,
    HIGH_THRESHOLD,
    MEDIUM_THRESHOLD,
    ConfidenceWeights,
)
from forge.core.confidence.factors import ConfidenceFactors, compute_factors


@dataclass
class ConfidenceResult:
    score: float
    level: str
    factors: ConfidenceFactors
    recommendation: str
    explanation: list[str] = field(default_factory=list)


class ConfidenceScorer:
    """Compute session confidence from ProjectState snapshot."""

    def __init__(self, weights: ConfidenceWeights | None = None) -> None:
        self.weights = weights or DEFAULT_WEIGHTS

    def score(self, state: dict[str, Any]) -> ConfidenceResult:
        factors = compute_factors(state)
        w = self.weights
        raw = (
            w.base
            + w.compliance * factors.compliance_factor
            + w.evidence * factors.evidence_factor
            + w.history * factors.history_factor
            - factors.retry_penalty
            - factors.error_penalty
        )
        score = round(max(0.0, min(1.0, raw)), 2)
        level, recommendation = self._classify(score)
        explanation = self._explain(factors, score, level, recommendation, state)
        return ConfidenceResult(
            score=score,
            level=level,
            factors=factors,
            recommendation=recommendation,
            explanation=explanation,
        )

    @staticmethod
    def score_from_state(state: dict[str, Any]) -> float:
        """Convenience: score only (CLI stats compat)."""
        return ConfidenceScorer().score(state).score

    def _classify(self, score: float) -> tuple[str, str]:
        if score >= HIGH_THRESHOLD:
            return "high", "auto_execute"
        if score >= MEDIUM_THRESHOLD:
            return "medium", "needs_review"
        return "low", "block"

    def _explain(
        self,
        factors: ConfidenceFactors,
        score: float,
        level: str,
        recommendation: str,
        state: dict[str, Any],
    ) -> list[str]:
        lines = [
            f"综合置信度 {score:.0%}（{level}）→ {recommendation}",
            f"合规因子 {factors.compliance_factor:.2f} | 证据因子 {factors.evidence_factor:.2f}",
            f"历史因子 {factors.history_factor:.2f} | 重试惩罚 -{factors.retry_penalty:.2f}",
        ]
        if factors.error_penalty:
            lines.append(f"错误惩罚 -{factors.error_penalty:.2f}")
        retries = int(state.get("compliance_retry_count") or 0)
        if retries:
            lines.append(f"合规重试 {retries} 次")
        return lines
