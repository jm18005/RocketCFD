"""Post-processing sanity flags: negative drag, discontinuous sweep jumps, non-convergence."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

DEFAULT_DISCONTINUITY_THRESHOLD_PCT = 25.0
DEFAULT_CONVERGENCE_RESIDUAL = 1e-4


@dataclass
class SanityFlag:
    case_index: int
    message: str


@dataclass
class SanityReport:
    flags: list[SanityFlag] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return len(self.flags) == 0


def check_negative_drag(cd_values: list[float]) -> list[SanityFlag]:
    return [
        SanityFlag(i, f"Cd is negative ({cd:.4g}); check reference-area sign convention and mesh orientation.")
        for i, cd in enumerate(cd_values)
        if cd < 0.0
    ]


def check_discontinuities(
    x_values: list[float], y_values: list[float], threshold_pct: float = DEFAULT_DISCONTINUITY_THRESHOLD_PCT
) -> list[SanityFlag]:
    """Flags adjacent sweep points (sorted by x_values) whose y_values jump by more than
    threshold_pct of the larger neighbor's magnitude, a sign of a non-converged or
    misconfigured case rather than genuine physics."""
    if len(x_values) < 2:
        return []
    order = np.argsort(x_values)
    y_sorted = np.asarray(y_values)[order]
    flags = []
    for i in range(1, len(y_sorted)):
        a, b = y_sorted[i - 1], y_sorted[i]
        scale = max(abs(a), abs(b), 1e-9)
        jump_pct = abs(b - a) / scale * 100.0
        if jump_pct > threshold_pct:
            flags.append(
                SanityFlag(
                    int(order[i]),
                    f"Discontinuous jump of {jump_pct:.0f}% between adjacent sweep points "
                    f"({a:.4g} -> {b:.4g}).",
                )
            )
    return flags


def check_convergence(
    residual_history: list[float], threshold: float = DEFAULT_CONVERGENCE_RESIDUAL
) -> SanityFlag | None:
    if not residual_history:
        return SanityFlag(-1, "No residual history found; cannot confirm convergence.")
    final = residual_history[-1]
    if final > threshold:
        return SanityFlag(-1, f"Final residual {final:.2e} is above the convergence threshold {threshold:.2e}.")
    return None


def build_sanity_report(
    cd_values: list[float], x_values: list[float], discontinuity_threshold_pct: float = DEFAULT_DISCONTINUITY_THRESHOLD_PCT
) -> SanityReport:
    flags = check_negative_drag(cd_values) + check_discontinuities(x_values, cd_values, discontinuity_threshold_pct)
    return SanityReport(sorted(flags, key=lambda f: f.case_index))
