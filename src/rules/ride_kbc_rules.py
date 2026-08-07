from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


RULE_NAME = "REPEATED_CUSTOMER_DRIVER"


@dataclass(frozen=True)
class KbcRuleConfig:
    high_ghost_rate: float = 0.3
    superfast_gap_min: float = 5.0
    tight_pair_share_driver: float = 0.5
    tight_pair_share_customer: float = 0.5
    dominant_route_share: float = 0.5
    min_pair_trips_for_share_rule: int = 6
    min_component_size: int = 2

    def validate(self) -> None:
        if not 0 <= self.high_ghost_rate <= 1:
            raise ValueError("high_ghost_rate must be between 0 and 1.")
        if self.superfast_gap_min <= 0:
            raise ValueError("superfast_gap_min must be positive.")
        if not 0 <= self.tight_pair_share_driver <= 1:
            raise ValueError("tight_pair_share_driver must be between 0 and 1.")
        if not 0 <= self.tight_pair_share_customer <= 1:
            raise ValueError("tight_pair_share_customer must be between 0 and 1.")
        if not 0 <= self.dominant_route_share <= 1:
            raise ValueError("dominant_route_share must be between 0 and 1.")
        if self.min_pair_trips_for_share_rule < 2:
            raise ValueError("min_pair_trips_for_share_rule must be at least 2.")
        if self.min_component_size < 1:
            raise ValueError("min_component_size must be at least 1.")


def annotate_kbc_signals(pair_stats: pd.DataFrame, config: KbcRuleConfig) -> pd.DataFrame:
    config.validate()
    if pair_stats.empty:
        return pair_stats.copy()

    enriched = pair_stats.copy()
    if "ghost_rate" not in enriched.columns:
        enriched["ghost_rate"] = 0.0
    if "min_gap_min" not in enriched.columns:
        enriched["min_gap_min"] = pd.NA
    return enriched.assign(
        high_confidence=(enriched["ghost_rate"] > config.high_ghost_rate)
        | (pd.to_numeric(enriched["min_gap_min"], errors="coerce") < config.superfast_gap_min)
    )


def apply_kbc_rules(pair_stats: pd.DataFrame, config: KbcRuleConfig) -> pd.DataFrame:
    enriched = annotate_kbc_signals(pair_stats, config)
    if enriched.empty:
        return enriched

    reason_frames: list[pd.DataFrame] = []

    def append_reason(mask: pd.Series, reason_code: str, flag_reason: str, supporting_signal: str) -> None:
        subset = enriched.loc[mask].copy()
        if subset.empty:
            return
        subset["rule_name"] = RULE_NAME
        subset["reason_code"] = reason_code
        subset["flag_reason"] = flag_reason
        subset["supporting_signal"] = supporting_signal
        reason_frames.append(subset)

    append_reason(
        enriched["is_extreme_volume"],
        "KB-C_EXTREME_VOLUME",
        "Driver-customer pair is an extreme weighted edge in the current analysis window.",
        "weighted_edge_outlier",
    )
    append_reason(
        (enriched["n_trips"] >= config.min_pair_trips_for_share_rule)
        & (enriched["pair_share_driver"] >= config.tight_pair_share_driver)
        & (enriched["pair_share_customer"] >= config.tight_pair_share_customer),
        "KB-C_TIGHT_PAIR_SHARE",
        "The pair absorbs an unusually large share of both the driver and customer activity.",
        "bipartite_pair_concentration",
    )
    if "component_size" in enriched.columns:
        append_reason(
            enriched["component_size"] >= config.min_component_size,
            "KB-C_SUSPICIOUS_COMPONENT",
            "The suspicious pair belongs to a connected component with shared supporting entities.",
            "wcc_component_support",
        )
    if "ghost_rate" in enriched.columns:
        append_reason(
            enriched["ghost_rate"] > config.high_ghost_rate,
            "KB-C_HIGH_GHOST_RATE",
            "Driver-customer pair has a high share of ghost trips with avg_kmh = 0.",
            "ghost_trip_density",
        )
    if "min_gap_min" in enriched.columns:
        append_reason(
            pd.to_numeric(enriched["min_gap_min"], errors="coerce") < config.superfast_gap_min,
            "KB-C_SUPERFAST_GAP",
            "Driver-customer pair creates consecutive trips too quickly to look operationally normal.",
            "temporal_turnaround",
        )
    if "dominant_route_share" in enriched.columns:
        append_reason(
            (enriched["n_trips"] >= config.min_pair_trips_for_share_rule)
            & (enriched["dominant_route_share"] >= config.dominant_route_share),
            "KB-C_ROUTE_LOOP",
            "The pair repeatedly cycles through the same pickup-dropoff route at suspicious density.",
            "route_loop_reuse",
        )

    if not reason_frames:
        return pd.DataFrame()
    return pd.concat(reason_frames, ignore_index=True)
