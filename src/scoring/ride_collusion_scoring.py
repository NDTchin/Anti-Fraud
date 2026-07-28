from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def score_pairs(pair_stats: pd.DataFrame) -> pd.DataFrame:
    if pair_stats.empty:
        result = pair_stats.copy()
        result["rule_score"] = pd.Series(dtype=float)
        return result

    threshold_floor = pair_stats["trip_threshold"].clip(lower=1.0)
    trip_strength = np.clip(pair_stats["n_trips"] / threshold_floor, 0, 5) / 5
    ghost_strength = np.clip(pair_stats["ghost_rate"] / 0.3, 0, 2) / 2
    fast_gap_strength = np.clip(5.0 / pair_stats["min_gap_min"].clip(lower=0.1), 0, 5) / 5
    share_strength = (
        np.clip(pair_stats["pair_share_driver"] / 0.5, 0, 2)
        + np.clip(pair_stats["pair_share_customer"] / 0.5, 0, 2)
    ) / 4
    route_strength = np.clip(pair_stats["dominant_route_share"] / 0.5, 0, 2) / 2
    score = 100 * (0.35 * trip_strength + 0.25 * ghost_strength + 0.2 * fast_gap_strength + 0.1 * share_strength + 0.1 * route_strength)
    return pair_stats.assign(rule_score=score.round(2))


def build_flagged_orders(active_orders: pd.DataFrame, pair_reason_rows: pd.DataFrame) -> pd.DataFrame:
    if pair_reason_rows.empty:
        return pd.DataFrame()

    columns = [
        "driver_id",
        "customer_id",
        "rule_name",
        "reason_code",
        "flag_reason",
        "supporting_signal",
        "n_trips",
        "n_ghost",
        "min_gap_min",
        "ghost_rate",
        "high_confidence",
        "avg_gmv",
        "total_gmv",
        "total_discount",
        "pair_share_driver",
        "pair_share_customer",
        "dominant_route_key",
        "dominant_route_share",
        "trip_threshold",
        "rule_score",
        "active_days",
        "latest_order_date",
        "top_service_name",
        "top_pickup_province_name",
        "top_dropoff_province_name",
    ]
    flagged = active_orders.merge(pair_reason_rows[columns], on=["driver_id", "customer_id"], how="inner")
    return flagged.assign(
        domain="ride",
        rule_version="kbc_v1",
        risk_tier=np.where(flagged["high_confidence"], "HIGH", "MEDIUM"),
        merchant_id=pd.NA,
        promotion_code=flagged["promotion_code"].fillna(""),
        customer_repeat_ratio=flagged["pair_share_customer"],
        pair_ratio=flagged["pair_share_driver"],
        pair_orders=flagged["n_trips"],
        flagged_at=pd.Timestamp.utcnow().isoformat(),
        evidence_json=flagged.apply(
            lambda row: {
                "driver_id": row["driver_id"],
                "customer_id": row["customer_id"],
                "n_trips": int(row["n_trips"]),
                "n_ghost": int(row["n_ghost"]),
                "min_gap_min": None if pd.isna(row["min_gap_min"]) else round(float(row["min_gap_min"]), 3),
                "ghost_rate": round(float(row["ghost_rate"]), 4),
                "pair_share_driver": round(float(row["pair_share_driver"]), 4),
                "pair_share_customer": round(float(row["pair_share_customer"]), 4),
                "dominant_route_share": round(float(row["dominant_route_share"]), 4),
                "high_confidence": bool(row["high_confidence"]),
                "dominant_route_key": row["dominant_route_key"],
            },
            axis=1,
        ),
    )


def summarize_daily_flags(flagged_orders: pd.DataFrame) -> pd.DataFrame:
    if flagged_orders.empty:
        return pd.DataFrame(
            columns=[
                "domain",
                "order_date",
                "rule_name",
                "flagged_orders",
                "flagged_customers",
                "model_overlap_orders",
                "total_gmv",
                "total_discount",
            ]
        )

    base = flagged_orders.drop_duplicates(["order_id", "rule_name"]).copy()
    return (
        base.groupby(["domain", "order_date", "rule_name"], dropna=False)
        .agg(
            flagged_orders=("order_id", "nunique"),
            flagged_customers=("customer_id", "nunique"),
            model_overlap_orders=("order_id", lambda values: 0),
            total_gmv=("gmv", "sum"),
            total_discount=("discount", "sum"),
        )
        .reset_index()
        .sort_values(["order_date", "flagged_orders"], ascending=[True, False])
    )


def build_rule_model_comparison(flagged_orders: pd.DataFrame) -> pd.DataFrame:
    if flagged_orders.empty:
        return pd.DataFrame(
            columns=[
                "domain",
                "rule_name",
                "flagged_orders",
                "flagged_customers",
                "avg_rule_score",
                "model_overlap_orders",
                "model_overlap_rate",
                "avg_anomaly_score",
            ]
        )
    base = flagged_orders.drop_duplicates(["order_id", "rule_name"]).copy()
    summary = (
        base.groupby(["domain", "rule_name"], dropna=False)
        .agg(
            flagged_orders=("order_id", "nunique"),
            flagged_customers=("customer_id", "nunique"),
            avg_rule_score=("rule_score", "mean"),
        )
        .reset_index()
    )
    return summary.assign(model_overlap_orders=0, model_overlap_rate=0.0, avg_anomaly_score=0.0)


def build_priority_recommendations(flagged_orders: pd.DataFrame) -> pd.DataFrame:
    if flagged_orders.empty:
        return pd.DataFrame(
            columns=[
                "domain",
                "rule_name",
                "priority_score",
                "recommendation",
                "flagged_orders",
                "avg_anomaly_score",
                "model_overlap_rate",
                "total_discount",
                "total_gmv",
            ]
        )
    base = flagged_orders.drop_duplicates(["order_id", "rule_name"]).copy()
    summary = (
        base.groupby(["domain", "rule_name"], dropna=False)
        .agg(
            flagged_orders=("order_id", "nunique"),
            total_discount=("discount", "sum"),
            total_gmv=("gmv", "sum"),
            avg_rule_score=("rule_score", "mean"),
            high_confidence_orders=("high_confidence", "sum"),
        )
        .reset_index()
    )
    summary = summary.assign(
        priority_score=(summary["avg_rule_score"] * 0.7 + summary["high_confidence_orders"] * 0.3).round(2),
        recommendation="Prioritize driver-customer pairs with high ghost rate or sub-5-minute repeat gaps; verify timeline and route-loop evidence in Neo4j.",
        avg_anomaly_score=0.0,
        model_overlap_rate=0.0,
    )
    return summary.sort_values(["priority_score", "flagged_orders"], ascending=False)


def build_quality_report(
    raw_orders: pd.DataFrame,
    active_orders: pd.DataFrame,
    pair_stats: pd.DataFrame,
    trip_threshold: float,
    flagged_orders: pd.DataFrame,
) -> pd.DataFrame:
    rows = [
        {"metric": "raw_orders", "value": int(len(raw_orders))},
        {"metric": "active_orders", "value": int(len(active_orders))},
        {"metric": "candidate_pairs", "value": int(len(pair_stats))},
        {"metric": "trip_threshold_q9999", "value": float(trip_threshold)},
        {"metric": "flagged_pairs", "value": int(pair_stats[["driver_id", "customer_id"]].drop_duplicates().shape[0])},
        {"metric": "flagged_rows", "value": int(len(flagged_orders))},
        {"metric": "high_confidence_pairs", "value": int(pair_stats["high_confidence"].sum()) if not pair_stats.empty else 0},
    ]
    return pd.DataFrame(rows)


def evaluate_known_pairs(flagged_orders: pd.DataFrame, known_pairs: pd.DataFrame) -> pd.DataFrame:
    if flagged_orders.empty or known_pairs.empty:
        return pd.DataFrame()

    pair_hits = flagged_orders[
        ["driver_id", "customer_id", "reason_code", "high_confidence", "n_trips", "ghost_rate", "min_gap_min"]
    ].drop_duplicates()
    evaluation = known_pairs.merge(pair_hits, on=["driver_id", "customer_id"], how="left")
    return evaluation.assign(is_flagged=evaluation["reason_code"].notna())
