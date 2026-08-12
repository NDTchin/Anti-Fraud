from __future__ import annotations

import pandas as pd

from src.algorithms.ride_collusion_graph import (
    RideCollusionGraphConfig,
    SuspiciousPairConfig,
    build_pair_stats,
    enrich_suspicious_pair_details,
    prepare_active_orders,
    shortlist_suspicious_pairs,
)
from src.rules.ride_kbc_rules import KbcRuleConfig, annotate_kbc_signals, apply_kbc_rules
from src.scoring.ride_collusion_scoring import (
    build_pair_scoring_features,
    build_graph_quality_reports,
    build_flagged_orders,
    enrich_pair_graph_features,
    finalize_business_rule_assignment,
    score_pairs,
    score_business_rules,
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
    rule_config = KbcRuleConfig(
        high_ghost_rate=0.3,
        superfast_gap_min=5.0,
        min_pair_trips_for_share_rule=3,
        dominant_route_share=0.5,
        min_high_confidence_trips=3,
        min_superfast_trips=3,
    )
    pair_stats, _, _ = build_pair_stats(active, graph_config)
    pair_stats = score_pairs(pair_stats)
    pair_stats = shortlist_suspicious_pairs(
        pair_stats,
        SuspiciousPairConfig(
            min_pair_trips=3,
            min_concentration_score=0.5,
            min_pair_core_score=35.0,
            min_ghost_rate=0.3,
            min_repeat_share_driver=0.3,
            min_repeat_share_customer=0.3,
        ),
    )
    pair_stats = enrich_suspicious_pair_details(active, pair_stats)
    pair_stats = annotate_kbc_signals(pair_stats, rule_config)
    pair_stats = build_pair_scoring_features(pair_stats)
    pair_stats = score_business_rules(pair_stats)
    reason_rows = apply_kbc_rules(pair_stats, rule_config)
    pair_stats = finalize_business_rule_assignment(pair_stats, reason_rows)
    flagged_orders = build_flagged_orders(active, reason_rows)
    daily = summarize_daily_flags(flagged_orders)

    assert pair_stats.iloc[0]["driver_id"] == "d1"
    assert pair_stats.iloc[0]["customer_id"] == "c1"
    assert pair_stats.iloc[0]["n_trips"] == 3
    assert pair_stats.iloc[0]["n_ghost"] == 2
    assert round(float(pair_stats.iloc[0]["ghost_rate"]), 4) == round(2 / 3, 4)
    assert round(float(pair_stats.iloc[0]["min_gap_min"]), 1) == 0.9
    assert bool(pair_stats.iloc[0]["high_confidence"]) is True
    assert round(float(pair_stats.iloc[0]["pair_core_score"]), 2) > 40
    assert pair_stats.iloc[0]["business_rule_label"] == "Dấu hiệu đơn ảo hoặc quay đầu bất thường"
    assert {"KB-C_EXTREME_VOLUME", "KB-C_HIGH_GHOST_RATE", "KB-C_SUPERFAST_GAP", "KB-C_TIGHT_PAIR_SHARE", "KB-C_ROUTE_LOOP"} <= set(reason_rows["reason_code"])
    assert {"Cặp lặp lại và phụ thuộc bất thường", "Dấu hiệu đơn ảo hoặc quay đầu bất thường", "Mẫu farming theo tuyến"} <= set(reason_rows["business_rule_label"])
    assert flagged_orders["order_id"].nunique() == 3
    assert int(daily["flagged_orders"].sum()) == 3


def test_enrich_suspicious_pair_details_sorts_before_gap_diff() -> None:
    active = pd.DataFrame(
        [
            {
                "order_id": "o2",
                "driver_id": "d1",
                "customer_id": "c1",
                "order_time_local_tz": pd.Timestamp("2026-07-14T10:00:54"),
                "pickup_address": "A",
                "last_dropoff_address": "B",
                "route_key": "A -> B",
            },
            {
                "order_id": "o1",
                "driver_id": "d1",
                "customer_id": "c1",
                "order_time_local_tz": pd.Timestamp("2026-07-14T10:00:00"),
                "pickup_address": "A",
                "last_dropoff_address": "B",
                "route_key": "A -> B",
            },
            {
                "order_id": "o3",
                "driver_id": "d1",
                "customer_id": "c1",
                "order_time_local_tz": pd.Timestamp("2026-07-14T10:02:00"),
                "pickup_address": "A",
                "last_dropoff_address": "B",
                "route_key": "A -> B",
            },
        ]
    )
    suspicious_pairs = pd.DataFrame(
        [
            {
                "driver_id": "d1",
                "customer_id": "c1",
                "n_trips": 3,
            }
        ]
    )

    enriched = enrich_suspicious_pair_details(active, suspicious_pairs)

    assert round(float(enriched.iloc[0]["min_gap_min"]), 1) == 0.9


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


def test_graph_support_requires_more_than_single_hub_signal() -> None:
    active = pd.DataFrame(
        [
            {
                "order_id": "o1",
                "driver_id": "d1",
                "customer_id": "c1",
                "payment_method": "cash",
                "promotion_code": "PROMO_GLOBAL",
                "pickup_address": "A",
                "last_dropoff_address": "B",
                "route_key": "A -> B",
            },
            {
                "order_id": "o2",
                "driver_id": "d2",
                "customer_id": "c2",
                "payment_method": "wallet",
                "promotion_code": "PROMO_GLOBAL",
                "pickup_address": "X",
                "last_dropoff_address": "Y",
                "route_key": "X -> Y",
            },
            {
                "order_id": "o3",
                "driver_id": "d3",
                "customer_id": "c3",
                "payment_method": "cash",
                "promotion_code": "PROMO_GLOBAL",
                "pickup_address": "A",
                "last_dropoff_address": "Z",
                "route_key": "A -> Z",
            },
        ]
    )
    pair_stats = pd.DataFrame(
        [
            {"driver_id": "d1", "customer_id": "c1", "pair_core_score": 70.0, "n_trips": 5},
            {"driver_id": "d2", "customer_id": "c2", "pair_core_score": 65.0, "n_trips": 4},
            {"driver_id": "d3", "customer_id": "c3", "pair_core_score": 68.0, "n_trips": 5},
        ]
    )

    enriched = enrich_pair_graph_features(active, pair_stats)
    quality = build_graph_quality_reports(active, pair_stats)
    by_pair = enriched.set_index(["driver_id", "customer_id"])
    metrics = quality["graph_quality"].set_index("metric")["value"]

    assert int(metrics["graph_edges"]) == 0
    assert int(metrics["component_count"]) == 3
    assert float(metrics["largest_component_share"]) == 0.3333
    assert int(by_pair.loc[("d2", "c2"), "linked_pair_count"]) == 0
    assert int(by_pair.loc[("d1", "c1"), "linked_pair_count"]) == 0
    assert int(by_pair.loc[("d3", "c3"), "linked_pair_count"]) == 0


def test_graph_support_requires_temporal_overlap_for_shared_entities() -> None:
    active = pd.DataFrame(
        [
            {
                "order_id": "o1",
                "driver_id": "d1",
                "customer_id": "c1",
                "payment_method": "wallet",
                "promotion_code": "P1",
                "pickup_address": "A",
                "last_dropoff_address": "B",
                "route_key": "A -> B",
                "order_date": "2026-07-24",
            },
            {
                "order_id": "o2",
                "driver_id": "d1",
                "customer_id": "c1",
                "payment_method": "wallet",
                "promotion_code": "P1",
                "pickup_address": "A",
                "last_dropoff_address": "B",
                "route_key": "A -> B",
                "order_date": "2026-07-24",
            },
            {
                "order_id": "o3",
                "driver_id": "d2",
                "customer_id": "c2",
                "payment_method": "wallet",
                "promotion_code": "P1",
                "pickup_address": "A",
                "last_dropoff_address": "B",
                "route_key": "A -> B",
                "order_date": "2026-07-29",
            },
            {
                "order_id": "o4",
                "driver_id": "d2",
                "customer_id": "c2",
                "payment_method": "wallet",
                "promotion_code": "P1",
                "pickup_address": "A",
                "last_dropoff_address": "B",
                "route_key": "A -> B",
                "order_date": "2026-07-29",
            },
        ]
    )
    pair_stats = pd.DataFrame(
        [
            {"driver_id": "d1", "customer_id": "c1", "pair_core_score": 70.0, "pair_collusion_score": 70.0, "suspected_ghost_score": 80.0, "n_trips": 5},
            {"driver_id": "d2", "customer_id": "c2", "pair_core_score": 65.0, "pair_collusion_score": 65.0, "suspected_ghost_score": 75.0, "n_trips": 4},
        ]
    )

    enriched = enrich_pair_graph_features(active, pair_stats)
    quality = build_graph_quality_reports(active, pair_stats)
    by_pair = enriched.set_index(["driver_id", "customer_id"])
    metrics = quality["graph_quality"].set_index("metric")["value"]

    assert int(metrics["graph_edges"]) == 0
    assert int(metrics["component_count"]) == 2
    assert int(by_pair.loc[("d1", "c1"), "linked_pair_count"]) == 0
    assert int(by_pair.loc[("d2", "c2"), "linked_pair_count"]) == 0
