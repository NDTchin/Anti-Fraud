from __future__ import annotations

import pandas as pd

from src.algorithms.ride_collusion_graph import (
    RideCollusionGraphConfig,
    build_pair_stats,
    prepare_active_orders,
)
from src.rules.ride_kbc_rules import KbcRuleConfig, annotate_kbc_signals, apply_kbc_rules
from src.scoring.ride_collusion_scoring import (
    build_flagged_orders,
    score_pairs,
    summarize_daily_flags,
)


def test_build_pair_stats_and_reasons_for_kbc_case() -> None:
    raw = pd.DataFrame(
        [
            {
                "order_id": "o1",
                "driver_id": "d1",
                "customer_id": "c1",
                "order_status": "COMPLETED",
                "order_time_local_tz": "2026-07-14T10:00:00",
                "pickup_completed_at_local_tz": "2026-07-14T10:01:00",
                "complete_time_local_tz": "2026-07-14T10:05:00",
                "service_name": "xanhsm_taxi",
                "pickup_province_name": "HCM",
                "pickup_district_name": "D1",
                "pickup_address": "A",
                "last_dropoff_province_name": "HCM",
                "last_dropoff_district_name": "D1",
                "last_dropoff_address": "B",
                "avg_kmh": 0.0,
                "gmv": 12000.0,
                "discount": 5000.0,
                "promotion_code": "P1",
                "payment_method": "cash",
                "order_date": "2026-07-14",
            },
            {
                "order_id": "o2",
                "driver_id": "d1",
                "customer_id": "c1",
                "order_status": "COMPLETED",
                "order_time_local_tz": "2026-07-14T10:00:54",
                "pickup_completed_at_local_tz": "2026-07-14T10:01:20",
                "complete_time_local_tz": "2026-07-14T10:06:00",
                "service_name": "xanhsm_taxi",
                "pickup_province_name": "HCM",
                "pickup_district_name": "D1",
                "pickup_address": "A",
                "last_dropoff_province_name": "HCM",
                "last_dropoff_district_name": "D1",
                "last_dropoff_address": "B",
                "avg_kmh": 0.0,
                "gmv": 12500.0,
                "discount": 5000.0,
                "promotion_code": "P1",
                "payment_method": "cash",
                "order_date": "2026-07-14",
            },
            {
                "order_id": "o3",
                "driver_id": "d1",
                "customer_id": "c1",
                "order_status": "COMPLETED",
                "order_time_local_tz": "2026-07-15T10:00:00",
                "pickup_completed_at_local_tz": "2026-07-15T10:01:00",
                "complete_time_local_tz": "2026-07-15T10:05:00",
                "service_name": "xanhsm_taxi",
                "pickup_province_name": "HCM",
                "pickup_district_name": "D1",
                "pickup_address": "A",
                "last_dropoff_province_name": "HCM",
                "last_dropoff_district_name": "D1",
                "last_dropoff_address": "B",
                "avg_kmh": 8.0,
                "gmv": 13000.0,
                "discount": 0.0,
                "promotion_code": "P1",
                "payment_method": "cash",
                "order_date": "2026-07-15",
            },
            {
                "order_id": "o4",
                "driver_id": "d2",
                "customer_id": "c2",
                "order_status": "COMPLETED",
                "order_time_local_tz": "2026-07-15T11:00:00",
                "pickup_completed_at_local_tz": "2026-07-15T11:01:00",
                "complete_time_local_tz": "2026-07-15T11:20:00",
                "service_name": "xanhsm_taxi",
                "pickup_province_name": "HCM",
                "pickup_district_name": "D3",
                "pickup_address": "C",
                "last_dropoff_province_name": "HCM",
                "last_dropoff_district_name": "D4",
                "last_dropoff_address": "D",
                "avg_kmh": 20.0,
                "gmv": 50000.0,
                "discount": 0.0,
                "promotion_code": "P2",
                "payment_method": "wallet",
                "order_date": "2026-07-15",
            },
        ]
    )
    raw["order_time_local_tz"] = pd.to_datetime(raw["order_time_local_tz"])
    raw["pickup_completed_at_local_tz"] = pd.to_datetime(raw["pickup_completed_at_local_tz"])
    raw["complete_time_local_tz"] = pd.to_datetime(raw["complete_time_local_tz"])

    active = prepare_active_orders(raw)
    graph_config = RideCollusionGraphConfig(extreme_trip_quantile=0.5)
    rule_config = KbcRuleConfig(high_ghost_rate=0.3, superfast_gap_min=5.0, min_pair_trips_for_share_rule=3)
    pair_stats, _, _ = build_pair_stats(active, graph_config)
    pair_stats = annotate_kbc_signals(pair_stats, rule_config)
    pair_stats = score_pairs(pair_stats)
    reason_rows = apply_kbc_rules(pair_stats, rule_config)
    flagged_orders = build_flagged_orders(active, reason_rows)
    daily = summarize_daily_flags(flagged_orders)

    assert pair_stats.iloc[0]["driver_id"] == "d1"
    assert pair_stats.iloc[0]["customer_id"] == "c1"
    assert pair_stats.iloc[0]["n_trips"] == 3
    assert pair_stats.iloc[0]["n_ghost"] == 2
    assert round(float(pair_stats.iloc[0]["ghost_rate"]), 4) == round(2 / 3, 4)
    assert round(float(pair_stats.iloc[0]["min_gap_min"]), 1) == 0.9
    assert bool(pair_stats.iloc[0]["high_confidence"]) is True
    assert {"KB-C_EXTREME_VOLUME", "KB-C_HIGH_GHOST_RATE", "KB-C_SUPERFAST_GAP", "KB-C_TIGHT_PAIR_SHARE", "KB-C_ROUTE_LOOP"} <= set(reason_rows["reason_code"])
    assert flagged_orders["order_id"].nunique() == 3
    assert int(daily["flagged_orders"].sum()) == 3


def test_prepare_active_orders_keeps_only_completed_status() -> None:
    raw = pd.DataFrame(
        [
            {
                "order_id": "completed_order",
                "driver_id": "d1",
                "customer_id": "c1",
                "order_status": "COMPLETED",
                "order_time_local_tz": "2026-07-14T10:00:00",
                "pickup_completed_at_local_tz": "2026-07-14T10:01:00",
                "complete_time_local_tz": "2026-07-14T10:05:00",
                "service_name": "xanhsm_taxi",
                "pickup_province_name": "HCM",
                "pickup_district_name": "D1",
                "pickup_address": "A",
                "last_dropoff_province_name": "HCM",
                "last_dropoff_district_name": "D1",
                "last_dropoff_address": "B",
                "avg_kmh": 12.0,
                "gmv": 12000.0,
                "discount": 0.0,
                "promotion_code": "P1",
                "payment_method": "cash",
                "order_date": "2026-07-14",
            },
            {
                "order_id": "cancelled_order",
                "driver_id": "d1",
                "customer_id": "c1",
                "order_status": "CANCELLED",
                "order_time_local_tz": "2026-07-14T10:10:00",
                "pickup_completed_at_local_tz": "2026-07-14T10:11:00",
                "complete_time_local_tz": "2026-07-14T10:15:00",
                "service_name": "xanhsm_taxi",
                "pickup_province_name": "HCM",
                "pickup_district_name": "D1",
                "pickup_address": "A",
                "last_dropoff_province_name": "HCM",
                "last_dropoff_district_name": "D1",
                "last_dropoff_address": "B",
                "avg_kmh": 0.0,
                "gmv": 12000.0,
                "discount": 0.0,
                "promotion_code": "P1",
                "payment_method": "cash",
                "order_date": "2026-07-14",
            },
        ]
    )

    active = prepare_active_orders(raw)

    assert active["order_id"].tolist() == ["completed_order"]
