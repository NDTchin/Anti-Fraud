from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd


def score_pairs(pair_stats: pd.DataFrame) -> pd.DataFrame:
    if pair_stats.empty:
        result = pair_stats.copy()
        result["rule_score_base"] = pd.Series(dtype=float)
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
    rounded = score.round(2)
    return pair_stats.assign(rule_score_base=rounded, rule_score=rounded)


@dataclass(frozen=True)
class RideGraphSignalConfig:
    payment_max_degree: int = 150
    promo_max_degree: int = 200
    address_max_degree: int = 50
    route_max_degree: int = 50
    component_size_cap: int = 10

    def validate(self) -> None:
        if self.payment_max_degree < 2:
            raise ValueError("payment_max_degree must be at least 2.")
        if self.promo_max_degree < 2:
            raise ValueError("promo_max_degree must be at least 2.")
        if self.address_max_degree < 2:
            raise ValueError("address_max_degree must be at least 2.")
        if self.route_max_degree < 2:
            raise ValueError("route_max_degree must be at least 2.")
        if self.component_size_cap < 2:
            raise ValueError("component_size_cap must be at least 2.")


def _pair_key_frame(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["pair_key"] = result["driver_id"].astype("string").str.strip() + "||" + result["customer_id"].astype("string").str.strip()
    return result


def _distinct_pair_entities(frame: pd.DataFrame, entity_column: str) -> pd.DataFrame:
    subset = frame[["pair_key", entity_column]].dropna().copy()
    if subset.empty:
        return subset
    subset[entity_column] = subset[entity_column].astype("string").str.strip()
    subset = subset[subset[entity_column] != ""]
    return subset.drop_duplicates()


def _signal_edges(
    frame: pd.DataFrame,
    entity_column: str,
    signal_name: str,
    max_degree: int,
) -> tuple[list[tuple[str, str, dict[str, object]]], dict[str, set[str]], dict[str, int]]:
    distinct = _distinct_pair_entities(frame, entity_column)
    if distinct.empty:
        return [], {}, {}

    grouped = distinct.groupby(entity_column, dropna=False)["pair_key"].agg(lambda values: sorted(set(values)))
    edges: list[tuple[str, str, dict[str, object]]] = []
    support_map: dict[str, set[str]] = {}
    entity_degrees: dict[str, int] = {}
    for entity_value, pair_keys in grouped.items():
        degree = len(pair_keys)
        if degree < 2 or degree > max_degree:
            continue
        entity_degrees[str(entity_value)] = degree
        for pair_key in pair_keys:
            support_map.setdefault(pair_key, set()).add(signal_name)
        for index, left in enumerate(pair_keys[:-1]):
            for right in pair_keys[index + 1 :]:
                edges.append(
                    (
                        left,
                        right,
                        {
                            "signal_type": signal_name,
                            "entity_value": str(entity_value),
                        },
                    )
                )
    return edges, support_map, entity_degrees


def enrich_pair_graph_features(
    active_orders: pd.DataFrame,
    pair_stats: pd.DataFrame,
    config: RideGraphSignalConfig | None = None,
) -> pd.DataFrame:
    graph_config = config or RideGraphSignalConfig()
    graph_config.validate()
    if pair_stats.empty:
        result = pair_stats.copy()
        result["shared_payment_count"] = pd.Series(dtype="int64")
        result["shared_promo_count"] = pd.Series(dtype="int64")
        result["shared_pickup_count"] = pd.Series(dtype="int64")
        result["shared_dropoff_count"] = pd.Series(dtype="int64")
        result["shared_route_count"] = pd.Series(dtype="int64")
        result["supporting_signal_count"] = pd.Series(dtype="int64")
        result["linked_pair_count"] = pd.Series(dtype="int64")
        result["component_id"] = pd.Series(dtype="string")
        result["component_size"] = pd.Series(dtype="int64")
        result["component_edge_count"] = pd.Series(dtype="int64")
        result["component_density"] = pd.Series(dtype=float)
        result["graph_risk_score"] = pd.Series(dtype=float)
        result["final_risk_score"] = pd.Series(dtype=float)
        return result

    pair_keys = _pair_key_frame(pair_stats[["driver_id", "customer_id"]])
    candidate_orders = active_orders.merge(pair_stats[["driver_id", "customer_id"]], on=["driver_id", "customer_id"], how="inner")
    candidate_orders = _pair_key_frame(candidate_orders)

    signal_specs = [
        ("payment_method", "payment", graph_config.payment_max_degree),
        ("promotion_code", "promo", graph_config.promo_max_degree),
        ("pickup_address", "pickup", graph_config.address_max_degree),
        ("last_dropoff_address", "dropoff", graph_config.address_max_degree),
        ("route_key", "route", graph_config.route_max_degree),
    ]

    graph = nx.Graph()
    graph.add_nodes_from(pair_keys["pair_key"].tolist())

    support_by_pair: dict[str, set[str]] = {}
    shared_counts = {
        "payment": {},
        "promo": {},
        "pickup": {},
        "dropoff": {},
        "route": {},
    }

    for entity_column, signal_name, max_degree in signal_specs:
        signal_edges, signal_support, entity_degrees = _signal_edges(
            candidate_orders,
            entity_column,
            signal_name,
            max_degree,
        )
        for pair_key, signal_names in signal_support.items():
            support_by_pair.setdefault(pair_key, set()).update(signal_names)
        for entity_value, degree in entity_degrees.items():
            shared_counts[signal_name][entity_value] = degree
        for left, right, attributes in signal_edges:
            if graph.has_edge(left, right):
                graph[left][right]["weight"] += 1
                graph[left][right]["signal_types"].add(attributes["signal_type"])
            else:
                graph.add_edge(left, right, weight=1, signal_types={attributes["signal_type"]})

    linked_pair_counts = {node: len(set(graph.neighbors(node))) for node in graph.nodes}
    component_rows: list[dict[str, object]] = []
    for index, component_nodes in enumerate(nx.connected_components(graph), start=1):
        component_graph = graph.subgraph(component_nodes)
        size = component_graph.number_of_nodes()
        edge_count = component_graph.number_of_edges()
        density = nx.density(component_graph) if size > 1 else 0.0
        component_id = f"ride_component_{index}"
        for node in component_nodes:
            component_rows.append(
                {
                    "pair_key": node,
                    "component_id": component_id,
                    "component_size": size,
                    "component_edge_count": edge_count,
                    "component_density": round(float(density), 4),
                }
            )
    components = pd.DataFrame(component_rows)

    def count_shared_entities(entity_column: str, max_degree: int) -> pd.DataFrame:
        distinct = _distinct_pair_entities(candidate_orders, entity_column)
        if distinct.empty:
            return pd.DataFrame(columns=["pair_key", entity_column])
        grouped = distinct.groupby(entity_column, dropna=False)["pair_key"].transform("nunique")
        filtered = distinct[(grouped >= 2) & (grouped <= max_degree)].copy()
        if filtered.empty:
            return pd.DataFrame(columns=["pair_key", entity_column])
        return (
            filtered.groupby("pair_key", dropna=False)[entity_column]
            .nunique()
            .reset_index()
        )

    payment_counts = count_shared_entities("payment_method", graph_config.payment_max_degree).rename(columns={"payment_method": "shared_payment_count"})
    promo_counts = count_shared_entities("promotion_code", graph_config.promo_max_degree).rename(columns={"promotion_code": "shared_promo_count"})
    pickup_counts = count_shared_entities("pickup_address", graph_config.address_max_degree).rename(columns={"pickup_address": "shared_pickup_count"})
    dropoff_counts = count_shared_entities("last_dropoff_address", graph_config.address_max_degree).rename(columns={"last_dropoff_address": "shared_dropoff_count"})
    route_counts = count_shared_entities("route_key", graph_config.route_max_degree).rename(columns={"route_key": "shared_route_count"})

    enriched = pair_stats.merge(pair_keys, on=["driver_id", "customer_id"], how="left")
    for counts in (payment_counts, promo_counts, pickup_counts, dropoff_counts, route_counts):
        enriched = enriched.merge(counts, on="pair_key", how="left")

    enriched = enriched.merge(components, on="pair_key", how="left")
    for column in (
        "shared_payment_count",
        "shared_promo_count",
        "shared_pickup_count",
        "shared_dropoff_count",
        "shared_route_count",
        "component_size",
        "component_edge_count",
    ):
        enriched[column] = enriched[column].fillna(0).astype(int)
    enriched["component_density"] = enriched["component_density"].fillna(0.0)
    enriched["component_id"] = enriched["component_id"].fillna(enriched["pair_key"])
    enriched["supporting_signal_count"] = enriched["pair_key"].map(lambda key: len(support_by_pair.get(key, set()))).fillna(0).astype(int)
    enriched["linked_pair_count"] = enriched["pair_key"].map(lambda key: linked_pair_counts.get(key, 0)).fillna(0).astype(int)

    linked_pair_strength = np.clip(enriched["linked_pair_count"] / 5.0, 0, 1)
    signal_strength = np.clip(enriched["supporting_signal_count"] / 5.0, 0, 1)
    component_size_strength = np.clip(enriched["component_size"] / graph_config.component_size_cap, 0, 1)
    density_strength = np.clip(enriched["component_density"], 0, 1)
    graph_score = 100 * (
        0.4 * linked_pair_strength
        + 0.25 * signal_strength
        + 0.2 * component_size_strength
        + 0.15 * density_strength
    )
    enriched["graph_risk_score"] = graph_score.round(2)

    base_score = enriched["rule_score_base"] if "rule_score_base" in enriched.columns else enriched["rule_score"]
    blended_score = 0.65 * base_score + 0.35 * enriched["graph_risk_score"]
    enriched["final_risk_score"] = np.maximum(base_score, blended_score).round(2)
    enriched["rule_score"] = enriched["final_risk_score"]
    return enriched.drop(columns=["pair_key"])


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
        "rule_score_base",
        "rule_score",
        "graph_risk_score",
        "final_risk_score",
        "shared_payment_count",
        "shared_promo_count",
        "shared_pickup_count",
        "shared_dropoff_count",
        "shared_route_count",
        "supporting_signal_count",
        "linked_pair_count",
        "component_id",
        "component_size",
        "component_edge_count",
        "component_density",
        "active_days",
        "latest_order_date",
        "top_service_name",
        "top_pickup_province_name",
        "top_dropoff_province_name",
    ]
    defaults: dict[str, object] = {
        "rule_score_base": pd.NA,
        "graph_risk_score": 0.0,
        "final_risk_score": pd.NA,
        "shared_payment_count": 0,
        "shared_promo_count": 0,
        "shared_pickup_count": 0,
        "shared_dropoff_count": 0,
        "shared_route_count": 0,
        "supporting_signal_count": 0,
        "linked_pair_count": 0,
        "component_id": pd.NA,
        "component_size": 0,
        "component_edge_count": 0,
        "component_density": 0.0,
    }
    pair_reason_rows = pair_reason_rows.copy()
    for column, value in defaults.items():
        if column not in pair_reason_rows.columns:
            pair_reason_rows[column] = value
    if pair_reason_rows["rule_score_base"].isna().all() and "rule_score" in pair_reason_rows.columns:
        pair_reason_rows["rule_score_base"] = pair_reason_rows["rule_score"]
    if pair_reason_rows["final_risk_score"].isna().all() and "rule_score" in pair_reason_rows.columns:
        pair_reason_rows["final_risk_score"] = pair_reason_rows["rule_score"]
    flagged = active_orders.merge(pair_reason_rows[columns], on=["driver_id", "customer_id"], how="inner")
    return flagged.assign(
        domain="ride",
        rule_version="kbc_v1",
        risk_tier=np.select(
            [
                flagged["high_confidence"] & flagged["final_risk_score"].ge(75),
                flagged["final_risk_score"].ge(60),
            ],
            ["HIGH", "MEDIUM"],
            default="WATCHLIST",
        ),
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
                "graph_risk_score": round(float(row["graph_risk_score"]), 2),
                "linked_pair_count": int(row["linked_pair_count"]),
                "supporting_signal_count": int(row["supporting_signal_count"]),
                "component_id": row["component_id"],
                "component_size": int(row["component_size"]),
                "component_density": round(float(row["component_density"]), 4),
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
                "avg_graph_risk_score",
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
            avg_graph_risk_score=("graph_risk_score", "mean"),
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
                "avg_graph_risk_score",
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
            avg_graph_risk_score=("graph_risk_score", "mean"),
            high_confidence_orders=("high_confidence", "sum"),
        )
        .reset_index()
    )
    summary = summary.assign(
        priority_score=(summary["avg_rule_score"] * 0.55 + summary["avg_graph_risk_score"] * 0.25 + summary["high_confidence_orders"] * 0.2).round(2),
        recommendation="Prioritize driver-customer pairs with strong ride-rule signals plus shared payment, promo, address, or route support inside the same suspicious component; verify component context in Neo4j.",
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
