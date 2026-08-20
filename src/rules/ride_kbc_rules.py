from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


RULE_NAME = "REPEATED_CUSTOMER_DRIVER"
BUSINESS_RULE_REPEATED_PAIR = "REPEATED_LOCKED_PAIR"
BUSINESS_RULE_GHOST_TRIP = "GHOST_TRIP_EXECUTION_PATTERN"
BUSINESS_RULE_ROUTE_FARMING = "ROUTE_FARMING_PATTERN"
BUSINESS_RULE_NETWORK = "COORDINATED_NETWORK_PATTERN"

BUSINESS_RULE_LABELS = {
    BUSINESS_RULE_REPEATED_PAIR: "Cặp lặp lại và phụ thuộc bất thường",
    BUSINESS_RULE_GHOST_TRIP: "Dấu hiệu đơn ảo hoặc quay đầu bất thường",
    BUSINESS_RULE_ROUTE_FARMING: "Mẫu farming theo tuyến",
    BUSINESS_RULE_NETWORK: "Cụm liên kết đáng ngờ nhiều cặp",
}

BUSINESS_RULE_STORIES = {
    BUSINESS_RULE_REPEATED_PAIR: "Tài xế và khách hàng đi với nhau nhiều lần và có mức độ phụ thuộc bất thường so với hành vi thông thường.",
    BUSINESS_RULE_GHOST_TRIP: "Cặp này có nhiều chuyến mang dấu hiệu đơn ảo, không di chuyển thật hoặc tạo chuyến quá sát nhau về thời gian.",
    BUSINESS_RULE_ROUTE_FARMING: "Cặp này lặp lại cùng một kiểu tuyến đường với mật độ đáng ngờ, giống hành vi farming hơn là di chuyển tự nhiên.",
    BUSINESS_RULE_NETWORK: "Cặp này nằm trong một cụm có nhiều cặp đáng ngờ khác cùng chia sẻ tín hiệu như địa điểm, tuyến, khuyến mãi hoặc phương thức thanh toán.",
}

REASON_CODE_TO_BUSINESS_RULE = {
    "KB-C_EXTREME_VOLUME": BUSINESS_RULE_REPEATED_PAIR,
    "KB-C_TIGHT_PAIR_SHARE": BUSINESS_RULE_REPEATED_PAIR,
    "KB-C_HIGH_GHOST_RATE": BUSINESS_RULE_GHOST_TRIP,
    "KB-C_SUPERFAST_GAP": BUSINESS_RULE_GHOST_TRIP,
    "KB-C_ROUTE_LOOP": BUSINESS_RULE_ROUTE_FARMING,
    "KB-C_SUSPICIOUS_COMPONENT": BUSINESS_RULE_NETWORK,
}


@dataclass(frozen=True)
class KbcRuleConfig:
    high_ghost_rate: float = 0.5
    superfast_gap_min: float = 2.0
    tight_pair_share_driver: float = 0.6
    tight_pair_share_customer: float = 0.6
    dominant_route_share: float = 0.7
    min_pair_trips_for_share_rule: int = 8
    min_component_size: int = 3
    min_high_confidence_trips: int = 4
    min_superfast_trips: int = 6
    min_network_linked_pairs: int = 2
    min_network_supporting_signals: int = 2

    def validate(self) -> None:
        if not 0 <= self.high_ghost_rate <= 1:
            raise ValueError("high_ghost_rate phải nằm trong khoảng 0 đến 1.")
        if self.superfast_gap_min <= 0:
            raise ValueError("superfast_gap_min phải là số dương.")
        if not 0 <= self.tight_pair_share_driver <= 1:
            raise ValueError("tight_pair_share_driver phải nằm trong khoảng 0 đến 1.")
        if not 0 <= self.tight_pair_share_customer <= 1:
            raise ValueError("tight_pair_share_customer phải nằm trong khoảng 0 đến 1.")
        if not 0 <= self.dominant_route_share <= 1:
            raise ValueError("dominant_route_share phải nằm trong khoảng 0 đến 1.")
        if self.min_pair_trips_for_share_rule < 2:
            raise ValueError("min_pair_trips_for_share_rule phải >= 2.")
        if self.min_component_size < 1:
            raise ValueError("min_component_size phải >= 1.")
        if self.min_high_confidence_trips < 1:
            raise ValueError("min_high_confidence_trips phải >= 1.")
        if self.min_superfast_trips < 2:
            raise ValueError("min_superfast_trips phải >= 2.")
        if self.min_network_linked_pairs < 1:
            raise ValueError("min_network_linked_pairs phải >= 1.")
        if self.min_network_supporting_signals < 1:
            raise ValueError("min_network_supporting_signals phải >= 1.")


def annotate_kbc_signals(pair_stats: pd.DataFrame, config: KbcRuleConfig) -> pd.DataFrame:
    config.validate()
    if pair_stats.empty:
        return pair_stats.copy()

    enriched = pair_stats.copy()
    if "ghost_rate" not in enriched.columns:
        enriched["ghost_rate"] = 0.0
    if "min_gap_min" not in enriched.columns:
        enriched["min_gap_min"] = pd.NA
    if "n_trips" not in enriched.columns:
        enriched["n_trips"] = 0
    min_gap = pd.to_numeric(enriched["min_gap_min"], errors="coerce")
    valid_superfast_gap = min_gap.ge(0) & min_gap.lt(config.superfast_gap_min)
    return enriched.assign(
        high_confidence=(
            (enriched["ghost_rate"] >= config.high_ghost_rate)
            & (enriched["n_trips"] >= config.min_high_confidence_trips)
        )
        | (
            valid_superfast_gap
            & (enriched["ghost_rate"] >= 0.2)
            & (enriched["n_trips"] >= config.min_superfast_trips)
        )
    )


def add_business_rule_metadata(frame: pd.DataFrame, reason_column: str = "reason_code") -> pd.DataFrame:
    if frame.empty or reason_column not in frame.columns:
        return frame.copy()
    enriched = frame.copy()
    enriched["business_rule"] = enriched[reason_column].map(REASON_CODE_TO_BUSINESS_RULE)
    enriched["business_rule_label"] = enriched["business_rule"].map(BUSINESS_RULE_LABELS)
    enriched["business_rule_story"] = enriched["business_rule"].map(BUSINESS_RULE_STORIES)
    return enriched


def apply_kbc_rules(pair_stats: pd.DataFrame, config: KbcRuleConfig) -> pd.DataFrame:
    enriched = annotate_kbc_signals(pair_stats, config)
    if enriched.empty:
        return enriched

    reason_frames: list[pd.DataFrame] = []
    n_trips = pd.to_numeric(enriched.get("n_trips"), errors="coerce").fillna(0)
    ghost_rate = pd.to_numeric(enriched.get("ghost_rate"), errors="coerce").fillna(0.0)
    min_gap = pd.to_numeric(enriched.get("min_gap_min"), errors="coerce")
    valid_superfast_gap = min_gap.ge(0) & min_gap.lt(config.superfast_gap_min)

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
        enriched["is_extreme_volume"]
        & (n_trips >= config.min_pair_trips_for_share_rule)
        & (
            (enriched["pair_share_driver"] >= config.tight_pair_share_driver)
            | (enriched["pair_share_customer"] >= config.tight_pair_share_customer)
        ),
        "KB-C_EXTREME_VOLUME",
        "Cặp tài xế - khách hàng này lặp lại với tần suất rất cao trong cửa sổ phân tích hiện tại.",
        "weighted_edge_outlier",
    )
    append_reason(
        (enriched["n_trips"] >= config.min_pair_trips_for_share_rule)
        & (enriched["pair_share_driver"] >= config.tight_pair_share_driver)
        & (enriched["pair_share_customer"] >= config.tight_pair_share_customer),
        "KB-C_TIGHT_PAIR_SHARE",
        "Cặp tài xế - khách hàng này chiếm tỷ trọng bất thường trong tổng hoạt động của cả tài xế và khách hàng.",
        "bipartite_pair_concentration",
    )
    if "component_size" in enriched.columns:
        append_reason(
            (enriched["component_size"] >= config.min_component_size)
            & (pd.to_numeric(enriched.get("linked_pair_count"), errors="coerce").fillna(0) >= config.min_network_linked_pairs)
            & (
                pd.to_numeric(enriched.get("supporting_signal_count"), errors="coerce").fillna(0)
                >= config.min_network_supporting_signals
            ),
            "KB-C_SUSPICIOUS_COMPONENT",
            "Cặp tài xế - khách hàng này nằm trong một nhóm liên kết đáng nghi và chia sẻ đầu mối với nhiều cặp khác.",
            "wcc_component_support",
        )
    if "ghost_rate" in enriched.columns:
        append_reason(
            (ghost_rate >= config.high_ghost_rate) & (n_trips >= config.min_high_confidence_trips),
            "KB-C_HIGH_GHOST_RATE",
            "Tỷ lệ ghost trip của cặp tài xế - khách hàng này cao, với nhiều chuyến có avg_kmh = 0.",
            "ghost_trip_density",
        )
    if "min_gap_min" in enriched.columns:
        append_reason(
            valid_superfast_gap
            & (ghost_rate >= 0.2)
            & (n_trips >= config.min_superfast_trips),
            "KB-C_SUPERFAST_GAP",
            "Cặp tài xế - khách hàng này tạo các chuyến liên tiếp quá nhanh, không giống vận hành bình thường.",
            "temporal_turnaround",
        )
    if "dominant_route_share" in enriched.columns:
        append_reason(
            (enriched["n_trips"] >= config.min_pair_trips_for_share_rule)
            & (enriched["dominant_route_share"] >= config.dominant_route_share),
            "KB-C_ROUTE_LOOP",
            "Cặp này lặp lại cùng một kiểu tuyến đường với mật độ đáng ngờ, giống hành vi farming hơn là di chuyển tự nhiên.",
            "route_loop_reuse",
        )

    if not reason_frames:
        return pd.DataFrame()
    return add_business_rule_metadata(pd.concat(reason_frames, ignore_index=True))
