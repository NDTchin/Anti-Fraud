from __future__ import annotations

import pandas as pd

from src.scoring.food_rules import (
    fixed_value_pattern_rule,
    food_fulfillment_time_outlier_rule,
    high_discount_outlier_rule,
    impossible_travel_rule,
    multi_link_driver_rule,
    repeated_customer_driver_rule,
)
from src.scoring.task3_rule_model import (
    daily_rule_summary,
    rule_model_comparison,
    run_rules,
    score_anomalies,
)


def sample_ride_orders() -> pd.DataFrame:
    rows = []
    for index in range(1005):
        rows.append(
            {
                "order_id": f"o{index + 1}",
                "customer_id": f"c{index + 1}",
                "driver_id": f"d{index + 1}",
                "domain": "ride",
                "order_date": "2026-07-14",
                "service_name": "BIKE",
                "km_ratio": 1.0,
                "avg_kmh": 30.0,
                "gmv": 100.0,
                "discount": 0.0,
                "declared_km": 5.0,
                "actual_km": 5.0,
                "intrip_time_second": 600.0,
            }
        )
    rows[-1]["km_ratio"] = 10.0
    rows[-1]["avg_kmh"] = 200.0
    rows[-1]["gmv"] = 10_000.0
    rows[-1]["discount"] = 500.0
    rows[-1]["actual_km"] = 50.0
    return pd.DataFrame(rows)


def sample_food_orders() -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    for index in range(20):
        rows.append(
            {
                "order_id": f"base{index}",
                "customer_id": f"base_customer_{index}",
                "driver_id": f"base_driver_{index}",
                "merchant_id": f"base_merchant_{index}",
                "promotion_code": pd.NA,
                "payment_method": "cash",
                "last_dropoff_address": f"base_addr_{index}",
                "pickup_province_name": "HCM",
                "domain": "food",
                "order_date": "2026-07-14",
                "service_name": "FOOD",
                "discount": 0.0,
                "lead_time_second": 300.0 + index,
                "gmv": 100000.0,
                "has_promotion": False,
                "order_time_local_tz": f"2026-07-14 07:{index:02d}:00",
                "food_total_order_amount": 100000.0 + index,
            }
        )

    promo_rows = [
        ("p1", "pc1", "d1", "m1", "P1", "momo", "A1", "HCM", 10000.0, 900.0, 50000.0, True, "2026-07-14 09:00:00", 120000.0),
        ("p2", "pc2", "d1", "m1", "P1", "momo", "A1", "HCM", 12000.0, 920.0, 52000.0, True, "2026-07-14 09:05:00", 121000.0),
        ("p3", "pc3", "d2", "m1", "P1", "momo", "A2", "HCM", 11000.0, 930.0, 53000.0, True, "2026-07-14 09:10:00", 122000.0),
        ("p4", "pc4", "d3", "m1", "P1", "momo", "A2", "HCM", 13000.0, 940.0, 54000.0, True, "2026-07-14 09:15:00", 123000.0),
        ("p5", "pc5", "d4", "m1", "P1", "cash", "A3", "HCM", 14000.0, 950.0, 55000.0, True, "2026-07-14 09:20:00", 124000.0),
    ]
    for order_id, customer_id, driver_id, merchant_id, promo, payment, address, province, discount, lead, gmv, has_promo, order_time, amount in promo_rows:
        rows.append(
            {
                "order_id": order_id,
                "customer_id": customer_id,
                "driver_id": driver_id,
                "merchant_id": merchant_id,
                "promotion_code": promo,
                "payment_method": payment,
                "last_dropoff_address": address,
                "pickup_province_name": province,
                "last_dropoff_province_name": province,
                "domain": "food",
                "order_date": "2026-07-14",
                "service_name": "FOOD",
                "discount": discount,
                "lead_time_second": lead,
                "gmv": gmv,
                "has_promotion": has_promo,
                "order_time_local_tz": order_time,
                "food_total_order_amount": amount,
            }
        )

    repeated_rows = [
        ("r1", "repeat_customer", "repeat_driver", "m9", pd.NA, "cash", "R1", "HCM", 0.0, 700.0, 60000.0, False, "2026-07-14 11:00:00", 61000.0),
        ("r2", "repeat_customer", "repeat_driver", "m9", pd.NA, "cash", "R1", "HCM", 0.0, 710.0, 60000.0, False, "2026-07-14 11:10:00", 62000.0),
        ("r3", "repeat_customer", "repeat_driver", "m9", pd.NA, "cash", "R2", "HCM", 0.0, 720.0, 60000.0, False, "2026-07-14 11:20:00", 63000.0),
    ]
    for order_id, customer_id, driver_id, merchant_id, promo, payment, address, province, discount, lead, gmv, has_promo, order_time, amount in repeated_rows:
        rows.append(
            {
                "order_id": order_id,
                "customer_id": customer_id,
                "driver_id": driver_id,
                "merchant_id": merchant_id,
                "promotion_code": promo,
                "payment_method": payment,
                "last_dropoff_address": address,
                "pickup_province_name": province,
                "last_dropoff_province_name": province,
                "domain": "food",
                "order_date": "2026-07-14",
                "service_name": "FOOD",
                "discount": discount,
                "lead_time_second": lead,
                "gmv": gmv,
                "has_promotion": has_promo,
                "order_time_local_tz": order_time,
                "food_total_order_amount": amount,
            }
        )

    fixed_rows = [
        ("fv1", "farm_customer_1", "link_driver", "farm_merchant_1", pd.NA, "card", "F1", "HCM", 10000.0, 800.0, 100000.0, False, "2026-07-14 12:00:00", 100000.0),
        ("fv2", "farm_customer_1", "link_driver", "farm_merchant_1", pd.NA, "card", "F1", "HCM", 10000.0, 810.0, 100000.0, False, "2026-07-14 12:10:00", 100500.0),
        ("fv3", "farm_customer_1", "link_driver", "farm_merchant_1", pd.NA, "card", "F1", "HCM", 10000.0, 820.0, 100000.0, False, "2026-07-14 12:20:00", 99800.0),
        ("fv4", "farm_customer_2", "link_driver", "farm_merchant_2", pd.NA, "card", "F2", "HCM", 12000.0, 830.0, 100000.0, False, "2026-07-14 12:30:00", 200000.0),
        ("fv5", "farm_customer_2", "link_driver", "farm_merchant_2", pd.NA, "card", "F2", "HCM", 12000.0, 840.0, 100000.0, False, "2026-07-14 12:40:00", 200200.0),
        ("fv6", "farm_customer_2", "link_driver", "farm_merchant_2", pd.NA, "card", "F2", "HCM", 12000.0, 850.0, 100000.0, False, "2026-07-14 12:50:00", 199900.0),
    ]
    for order_id, customer_id, driver_id, merchant_id, promo, payment, address, province, discount, lead, gmv, has_promo, order_time, amount in fixed_rows:
        rows.append(
            {
                "order_id": order_id,
                "customer_id": customer_id,
                "driver_id": driver_id,
                "merchant_id": merchant_id,
                "promotion_code": promo,
                "payment_method": payment,
                "last_dropoff_address": address,
                "pickup_province_name": province,
                "last_dropoff_province_name": province,
                "domain": "food",
                "order_date": "2026-07-14",
                "service_name": "FOOD",
                "discount": discount,
                "lead_time_second": lead,
                "gmv": gmv,
                "has_promotion": has_promo,
                "order_time_local_tz": order_time,
                "food_total_order_amount": amount,
            }
        )

    impossible_rows = [
        ("it1", "travel_customer", "td1", "mt1", pd.NA, "cash", "T1", "HCM", 0.0, 600.0, 50000.0, False, "2026-07-14 08:00:00", 51000.0),
        ("it2", "travel_customer", "td2", "mt2", pd.NA, "cash", "T2", "Ha Noi", 0.0, 610.0, 50000.0, False, "2026-07-14 10:00:00", 52000.0),
        ("it3", "travel_customer", "td3", "mt3", pd.NA, "cash", "T3", "Da Nang", 0.0, 620.0, 50000.0, False, "2026-07-14 12:30:00", 53000.0),
    ]
    for order_id, customer_id, driver_id, merchant_id, promo, payment, address, province, discount, lead, gmv, has_promo, order_time, amount in impossible_rows:
        rows.append(
            {
                "order_id": order_id,
                "customer_id": customer_id,
                "driver_id": driver_id,
                "merchant_id": merchant_id,
                "promotion_code": promo,
                "payment_method": payment,
                "last_dropoff_address": address,
                "pickup_province_name": province,
                "last_dropoff_province_name": province,
                "domain": "food",
                "order_date": "2026-07-14",
                "service_name": "FOOD",
                "discount": discount,
                "lead_time_second": lead,
                "gmv": gmv,
                "has_promotion": has_promo,
                "order_time_local_tz": order_time,
                "food_total_order_amount": amount,
            }
        )

    rows.append(
        {
            "order_id": "long1",
            "customer_id": "long_customer",
            "driver_id": "long_driver",
            "merchant_id": "long_merchant",
            "promotion_code": "LONGPROMO",
            "payment_method": "card",
            "last_dropoff_address": "L1",
            "pickup_province_name": "HCM",
            "domain": "food",
            "order_date": "2026-07-14",
            "service_name": "FOOD",
            "discount": 30000.0,
            "lead_time_second": 5000.0,
            "gmv": 40000.0,
            "has_promotion": True,
            "order_time_local_tz": "2026-07-14 13:00:00",
            "food_total_order_amount": 40000.0,
        }
    )

    return pd.DataFrame(rows)


def sample_legit_campaign_orders() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    order_index = 1
    for merchant_id, payment_prefix, address_prefix in (("m1", "pm1", "a1"), ("m2", "pm2", "a2"), ("m3", "pm3", "a3")):
        for customer_index in range(5):
            rows.append(
                {
                    "order_id": f"lc{order_index}",
                    "customer_id": f"cust_{merchant_id}_{customer_index}",
                    "driver_id": f"drv_{merchant_id}_{customer_index}",
                    "merchant_id": merchant_id,
                    "promotion_code": "PROMO_GLOBAL",
                    "payment_method": f"{payment_prefix}_{customer_index}",
                    "last_dropoff_address": f"{address_prefix}_{customer_index}",
                    "pickup_province_name": "HCM",
                    "domain": "food",
                    "order_date": "2026-07-14",
                    "service_name": "FOOD",
                    "discount": 8000.0,
                    "lead_time_second": 600.0 + customer_index,
                    "gmv": 60000.0,
                    "food_total_order_amount": 60000.0 + customer_index,
                    "has_promotion": True,
                    "order_time_local_tz": f"2026-07-14 10:{order_index:02d}:00",
                }
            )
            order_index += 1
    return pd.DataFrame(rows)


def test_repeated_customer_driver_rule_flags_repeated_food_pairs() -> None:
    repeated_food = pd.DataFrame(
        {
            "order_id": ["f1", "f2", "f3", "f4"],
            "customer_id": ["c1", "c1", "c1", "c2"],
            "driver_id": ["d1", "d1", "d1", "d2"],
            "merchant_id": ["m1", "m1", "m1", "m2"],
            "domain": ["food"] * 4,
            "order_date": ["2026-07-14"] * 4,
            "order_time_local_tz": [
                "2026-07-14 10:00:00",
                "2026-07-14 11:00:00",
                "2026-07-14 12:00:00",
                "2026-07-14 10:30:00",
            ],
        }
    )
    flags = repeated_customer_driver_rule(repeated_food)

    assert not flags.empty
    assert set(flags["rule_name"]) == {"REPEATED_CUSTOMER_DRIVER"}
    assert set(flags["reason_code"]) == {"REPEATED_DRIVER_SAME_MERCHANT"}
    assert "c1" in set(flags["customer_id"])
    assert {"pair_orders", "pair_ratio"}.issubset(flags.columns)


def test_impossible_travel_rule_requires_continuous_multi_hop_pattern() -> None:
    frame = pd.DataFrame(
        {
            "order_id": ["a", "b", "c", "d"],
            "customer_id": ["cust1", "cust1", "cust1", "cust2"],
            "merchant_id": ["m1", "m2", "m3", "m4"],
            "driver_id": ["d1", "d2", "d3", "d4"],
            "domain": ["food", "food", "food", "food"],
            "order_date": ["2026-07-14"] * 4,
            "order_time_local_tz": [
                "2026-07-14 08:00:00",
                "2026-07-14 10:00:00",
                "2026-07-14 12:30:00",
                "2026-07-14 09:00:00",
            ],
            "pickup_province_name": ["HCM", "Ha Noi", "Da Nang", "HCM"],
            "last_dropoff_province_name": ["HCM", "Ha Noi", "Da Nang", "HCM"],
            "is_completed": [True, True, True, True],
        }
    )

    flags = impossible_travel_rule(frame)

    assert set(flags["order_id"]) == {"b", "c"}
    assert set(flags["reason_code"]) == {"IMPOSSIBLE_TRAVEL_DELIVERY_ZONE_HOP"}
    assert flags["impossible_travel_count"].max() == 2


def test_high_discount_rule_requires_repeated_completed_or_cancelled_pattern() -> None:
    rows = []
    for index in range(40):
        rows.append(
            {
                "order_id": f"base_hd_{index}",
                "customer_id": f"base_customer_{index}",
                "merchant_id": f"base_merchant_{index}",
                "domain": "food",
                "order_date": "2026-07-14",
                "service_name": "FOOD",
                "discount": 1000.0,
                "gmv": 100000.0,
                "is_completed": True,
                "is_cancelled": False,
            }
        )
    for index in range(5):
        rows.append(
            {
                "order_id": f"hd_{index}",
                "customer_id": "repeat_hd_customer",
                "merchant_id": "repeat_hd_merchant",
                "domain": "food",
                "order_date": "2026-07-14",
                "service_name": "FOOD",
                "discount": 45000.0,
                "gmv": 50000.0,
                "is_completed": True,
                "is_cancelled": False,
            }
        )

    flags = high_discount_outlier_rule(pd.DataFrame(rows))

    assert set(flags["order_id"]) == {"hd_0", "hd_1", "hd_2", "hd_3", "hd_4"}
    assert set(flags["reason_code"]) == {"FOOD_HIGH_DISCOUNT_REPEAT_COMPLETED"}


def test_fulfillment_rule_requires_repeated_status_pattern() -> None:
    rows = []
    for index in range(40):
        rows.append(
            {
                "order_id": f"base_ft_{index}",
                "customer_id": f"base_customer_{index}",
                "merchant_id": f"base_merchant_{index}",
                "domain": "food",
                "order_date": "2026-07-14",
                "service_name": "FOOD",
                "lead_time_second": 500.0 + index,
                "discount": 0.0,
                "has_promotion": False,
                "is_completed": True,
                "is_cancelled": False,
            }
        )
    for index in range(5):
        rows.append(
            {
                "order_id": f"ft_{index}",
                "customer_id": "repeat_ft_customer",
                "merchant_id": "repeat_ft_merchant",
                "domain": "food",
                "order_date": "2026-07-14",
                "service_name": "FOOD",
                "lead_time_second": 8000.0,
                "discount": 15000.0,
                "has_promotion": True,
                "is_completed": False,
                "is_cancelled": True,
            }
        )

    flags = food_fulfillment_time_outlier_rule(pd.DataFrame(rows))

    assert set(flags["order_id"]) == {"ft_0", "ft_1", "ft_2", "ft_3", "ft_4"}
    assert set(flags["reason_code"]) == {"FOOD_LONG_FULFILLMENT_CANCEL_LOOP"}


def test_fixed_value_and_multi_link_driver_rules_flag_account_farm_patterns() -> None:
    frame = pd.DataFrame(
        {
            "order_id": ["o1", "o2", "o3", "o4", "o5", "o6"],
            "customer_id": ["c1", "c1", "c1", "c2", "c2", "c2"],
            "merchant_id": ["m1", "m1", "m1", "m2", "m2", "m2"],
            "driver_id": ["d_link", "d_link", "d_link", "d_link", "d_link", "d_link"],
            "domain": ["food"] * 6,
            "order_date": ["2026-07-14"] * 6,
            "food_total_order_amount": [100000.0, 100500.0, 99800.0, 200000.0, 200200.0, 199900.0],
            "discount": [10000.0, 10000.0, 10000.0, 12000.0, 12000.0, 12000.0],
        }
    )

    fixed_flags = fixed_value_pattern_rule(frame)
    driver_flags = multi_link_driver_rule(frame)

    assert {"c1", "c2"}.issubset(set(fixed_flags["customer_id"]))
    assert set(fixed_flags["reason_code"]).issubset({"FIXED_VALUE_PROMO_DRIVER_LOOP", "FIXED_VALUE_PROMO_BURST", "FIXED_VALUE_PROMO_ADDRESS_CLUSTER", "FIXED_VALUE_DRIVER_CANCEL_LOOP", "FIXED_VALUE_DRIVER_LOOP", "FIXED_VALUE_HIGH_DENSITY_REPEAT"})
    assert set(driver_flags["driver_id"]) == {"d_link"}
    assert set(driver_flags["reason_code"]).issubset({"DRIVER_MULTI_LINK_FARM", "DRIVER_MULTI_LINK_CORE", "DRIVER_MULTI_LINK_PROMO", "DRIVER_MULTI_LINK_DISCOUNT"})
    assert driver_flags["linked_pair_count"].max() >= 2


def test_task3_rule_model_outputs_are_joinable_for_ride() -> None:
    orders = sample_ride_orders()
    flags = run_rules(orders)
    anomalies = score_anomalies(orders)
    daily = daily_rule_summary(flags, anomalies)
    comparison = rule_model_comparison(flags, anomalies)

    assert {"order_id", "rule_name", "rule_score", "reason_code", "entity_reputation_score", "graph_risk_score", "segment_region"}.issubset(flags.columns)
    assert {"order_id", "anomaly_score", "is_model_anomaly", "model_version"}.issubset(anomalies.columns)
    assert anomalies["model_version"].str.contains("task3-baseline-v2").all()
    assert {"order_date", "rule_name", "flagged_orders"}.issubset(daily.columns)
    assert {"rule_name", "model_overlap_rate"}.issubset(comparison.columns)


def test_ride_repeated_customer_driver_rule_flags_dense_route_loop() -> None:
    frame = pd.DataFrame(
        {
            "order_id": ["r1", "r2", "r3", "r4"],
            "customer_id": ["cust1", "cust1", "cust1", "cust2"],
            "driver_id": ["drv1", "drv1", "drv1", "drv2"],
            "domain": ["ride"] * 4,
            "order_date": ["2026-07-14"] * 4,
            "order_time_local_tz": [
                "2026-07-14 08:00:00",
                "2026-07-14 09:00:00",
                "2026-07-14 10:00:00",
                "2026-07-14 11:00:00",
            ],
            "pickup_district_name": ["D1", "D1", "D1", "D2"],
            "last_dropoff_district_name": ["D3", "D3", "D3", "D4"],
            "promotion_code": ["PROMO1", "PROMO1", "PROMO1", pd.NA],
            "discount": [10000.0, 10000.0, 10000.0, 0.0],
            "is_cancelled": [False, False, False, False],
        }
    )

    from src.scoring.ride_rules import ride_repeated_customer_driver_rule

    flags = ride_repeated_customer_driver_rule(frame)

    assert not flags.empty
    assert set(flags["rule_name"]) == {"RIDE_REPEATED_CUSTOMER_DRIVER"}
    assert set(flags["reason_code"]) == {"RIDE_REPEAT_DRIVER_SAME_ROUTE"}


def test_ride_cancel_rebook_loop_flags_short_route_cluster() -> None:
    frame = pd.DataFrame(
        {
            "order_id": ["c1", "c2", "c3", "c4"],
            "customer_id": ["cust_cancel"] * 4,
            "domain": ["ride"] * 4,
            "order_date": ["2026-07-14"] * 4,
            "service_name": ["BIKE"] * 4,
            "order_time_local_tz": [
                "2026-07-14 08:00:00",
                "2026-07-14 08:45:00",
                "2026-07-14 09:20:00",
                "2026-07-14 10:10:00",
            ],
            "pickup_district_name": ["D1"] * 4,
            "last_dropoff_district_name": ["D2"] * 4,
            "promotion_code": ["PROMO2", "PROMO2", "PROMO2", pd.NA],
            "discount": [12000.0, 12000.0, 12000.0, 0.0],
            "is_cancelled": [True, True, True, True],
        }
    )

    from src.scoring.ride_rules import ride_cancel_rebook_loop_rule

    flags = ride_cancel_rebook_loop_rule(frame)

    assert not flags.empty
    assert set(flags["rule_name"]) == {"RIDE_CANCEL_REBOOK_LOOP"}
    assert set(flags["reason_code"]) == {"RIDE_PROMO_CANCEL_REBOOK"}


def test_run_rules_applies_food_rules_separately() -> None:
    flags = run_rules(sample_food_orders())
    promo_flags = flags[flags["rule_name"] == "PROMO_ENTITY_CONCENTRATION"]

    assert "PROMO_ENTITY_CONCENTRATION" in set(flags["rule_name"])
    assert "IMPOSSIBLE_TRAVEL" in set(flags["rule_name"])
    assert "FIXED_VALUE_PATTERN" in set(flags["rule_name"])
    assert "MULTI_LINK_DRIVER" not in set(flags["rule_name"])
    assert "REPEATED_CUSTOMER_DRIVER" in set(flags["rule_name"])
    assert "SERVICE_TRIP_OUTLIER" not in set(flags["rule_name"])
    assert {"shared_signal_count", "merchant_order_share", "payment_share", "entity_reputation_score", "graph_risk_score", "supporting_signal_count"}.issubset(promo_flags.columns)
    assert "reason_code" in promo_flags.columns


def test_run_rules_consolidates_overlapping_food_signals() -> None:
    flags = run_rules(sample_food_orders())

    linked_fixed = flags[flags["order_id"].isin(["fv1", "fv2", "fv3", "fv4", "fv5", "fv6"])]
    assert "MULTI_LINK_DRIVER" not in set(linked_fixed["rule_name"])
    assert "FIXED_VALUE_DRIVER_NETWORK" in set(linked_fixed["reason_code"])


def test_run_rules_drops_standalone_fulfillment_anomalies() -> None:
    rows = []
    for index in range(20):
        rows.append(
            {
                "order_id": f"b{index}",
                "customer_id": f"c{index}",
                "merchant_id": f"m{index}",
                "domain": "food",
                "order_date": "2026-07-14",
                "service_name": "FOOD",
                "lead_time_second": 300.0 + index,
            }
        )
    rows.append(
        {
            "order_id": "long_only",
            "customer_id": "cx",
            "merchant_id": "mx",
            "domain": "food",
            "order_date": "2026-07-14",
            "service_name": "FOOD",
            "lead_time_second": 8000.0,
        }
    )
    frame = pd.DataFrame(rows)

    flags = run_rules(frame)

    assert "FOOD_FULFILLMENT_TIME_OUTLIER" not in set(flags["rule_name"])


def test_legit_promo_campaign_is_not_flagged_as_concentration() -> None:
    flags = run_rules(sample_legit_campaign_orders())

    assert "PROMO_ENTITY_CONCENTRATION" not in set(flags["rule_name"])
