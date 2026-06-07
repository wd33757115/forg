"""Default weights and thresholds for ConfidenceScorer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConfidenceWeights:
    base: float = 0.28
    compliance: float = 0.40
    evidence: float = 0.25
    history: float = 0.15
    retry_per_event: float = 0.12
    retry_cap: float = 0.36
    error_per_event: float = 0.08
    error_cap: float = 0.24
    strict_mode_factor: float = 0.90


HIGH_THRESHOLD = 0.75
MEDIUM_THRESHOLD = 0.45

DEFAULT_WEIGHTS = ConfidenceWeights()
