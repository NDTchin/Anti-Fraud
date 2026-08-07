from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import networkx as nx
import numpy as np
import pandas as pd


def _safe_float(value: object, default: float = 0.0) -> float:
    if value is None or pd.isna(value):
        return default
    return float(value)


def score_pairs(pair_stats: pd.DataFrame) -> pd.DataFrame:
    if pair_stats.empty:
        result = pair_stats.copy()
        result["pair_core_score"] = pd.Series(dtype=float)
        result["pair_collusion_score"] = pd.Series(dtype=float)
        return result

    score = 100 * (0.45 * pair_stats["volume_score"] + 0.55 * pair_stats["concentration_score"])
    return pair_stats.assign(
        pair_core_score=score.round(2),
        pair_collusion_score=score.round(2),
    )


def build_pair_scoring_features(pair_stats: pd.DataFrame) -> pd.DataFrame:
    if pair_stats.empty:
        result = pair_stats.copy()
        for column in (
            "suspected_ghost_rate",
            "temporal_score",
            "avg_gmv_percentile_by_cohort",
            "low_value_farming_score",
            "suspected_ghost_score",
            "pair_risk_score",
            "business_impact_score",
            "fraud_risk_score",
            "investigation_priority_score",
        ):
            result[column] = pd.Series(dtype=float)
        return result

    enriched = pair_stats.copy()
    if "pair_collusion_score" not in enriched.columns and "pair_core_score" in enriched.columns:
        enriched["pair_collusion_score"] = enriched["pair_core_score"]

    gap_score = np.clip((30.0 - pd.to_numeric(enriched.get("min_gap_min"), errors="coerce").fillna(30.0)) / 30.0, 0, 1)
    route_score = pd.to_numeric(enriched.get("dominant_route_share"), errors="coerce").fillna(0.0).clip(0, 1)
    temporal_score = np.clip(0.7 * gap_score + 0.3 * route_score, 0, 1)

    value_cohort = (
        enriched.get("volume_cohort", pd.Series(["unknown"] * len(enriched), index=enriched.index))
        .astype("string")
        .fillna("unknown")
    )
    avg_gmv_percentile = (
        enriched.assign(_value_cohort=value_cohort)
        .groupby("_value_cohort", dropna=False)["avg_gmv"]
        .rank(method="max", pct=True)
        .fillna(0.0)
    )
    low_value_farming = np.clip(enriched["volume_score"].fillna(0.0) * (1 - avg_gmv_percentile), 0, 1)
    suspected_ghost_rate = pd.to_numeric(enriched.get("ghost_rate"), errors="coerce").fillna(0.0).clip(0, 1)
    suspected_ghost_score = 100 * (0.50 * suspected_ghost_rate + 0.30 * temporal_score + 0.20 * low_value_farming)
    pair_risk_score = 0.45 * enriched["pair_collusion_score"].fillna(enriched["pair_core_score"].fillna(0.0)) + 0.55 * suspected_ghost_score

    total_discount_pct = enriched["total_discount"].rank(method="max", pct=True).fillna(0.0)
    total_gmv_pct = enriched["total_gmv"].rank(method="max", pct=True).fillna(0.0)
    business_impact = 100 * (
        0.45 * total_discount_pct
        + 0.35 * total_gmv_pct
        + 0.20 * enriched["volume_score"].fillna(0.0)
    )

    return enriched.assign(
        suspected_ghost_rate=suspected_ghost_rate.round(4),
        temporal_score=temporal_score.round(4),
        avg_gmv_percentile_by_cohort=avg_gmv_percentile.round(4),
        low_value_farming_score=low_value_farming.round(4),
        suspected_ghost_score=suspected_ghost_score.round(2),
        pair_risk_score=pair_risk_score.round(2),
        business_impact_score=business_impact.round(2),
        fraud_risk_score=pair_risk_score.round(2),
        investigation_priority_score=pair_risk_score.round(2),
    )


@dataclass(frozen=True)
class RideGraphSignalConfig:
    payment_max_degree: int = 50
    promo_max_degree: int = 40
    address_max_degree: int = 25
    route_max_degree: int = 20
    component_size_cap: int = 10
    min_shared_signals: int = 2
    min_edge_weight: float = 1.35
    single_signal_min_weight: float = 1.75
    single_signal_min_shared_entities: int = 2
    max_entity_gap_days: int = 3

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
        if self.min_shared_signals < 1:
            raise ValueError("min_shared_signals must be at least 1.")
        if self.min_edge_weight <= 0:
            raise ValueError("min_edge_weight must be positive.")
        if self.single_signal_min_weight <= 0:
            raise ValueError("single_signal_min_weight must be positive.")
        if self.single_signal_min_shared_entities < 1:
            raise ValueError("single_signal_min_shared_entities must be at least 1.")
        if self.max_entity_gap_days < 0:
            raise ValueError("max_entity_gap_days must be at least 0.")


def _pair_key_frame(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["pair_key"] = result["driver_id"].astype("string").str.strip() + "||" + result["customer_id"].astype("string").str.strip()
    return result


def _normalize_entity_value(signal_name: str, value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    lowered = text.lower()
    if lowered in {"nan", "<na>", "none", "null", "unknown"}:
        return None
    if signal_name == "payment" and lowered in {"cash", "ti_n_mat", "tien_mat"}:
        return None
    if signal_name in {"pickup", "dropoff"} and lowered.replace(" ", "") in {
        "(0.000000,0.000000)",
        "(0.0,0.0)",
        "0,0",
        "0.0,0.0",
        "0.000000,0.000000",
    }:
        return None
    return text


def _distinct_pair_entities(frame: pd.DataFrame, entity_column: str, signal_name: str) -> pd.DataFrame:
    columns = ["pair_key", entity_column]
    if "order_date" in frame.columns:
        columns.append("order_date")
    subset = frame[columns].dropna(subset=["pair_key", entity_column]).copy()
    if subset.empty:
        return subset
    subset[entity_column] = subset[entity_column].map(lambda value: _normalize_entity_value(signal_name, value))
    subset = subset.dropna(subset=[entity_column])
    if subset.empty:
        return subset
    if "order_date" not in subset.columns:
        subset["first_order_date"] = pd.NaT
        subset["last_order_date"] = pd.NaT
        return subset.drop_duplicates()[["pair_key", entity_column, "first_order_date", "last_order_date"]]
    subset["order_date"] = pd.to_datetime(subset["order_date"], errors="coerce")
    return (
        subset.groupby(["pair_key", entity_column], dropna=False)
        .agg(first_order_date=("order_date", "min"), last_order_date=("order_date", "max"))
        .reset_index()
    )


def _graph_signal_specs(config: RideGraphSignalConfig) -> list[tuple[str, str, int, float]]:
    return [
        ("payment_method", "payment", config.payment_max_degree, 1.0),
        ("promotion_code", "promo", config.promo_max_degree, 0.85),
        ("pickup_address", "pickup", config.address_max_degree, 0.8),
        ("last_dropoff_address", "dropoff", config.address_max_degree, 0.8),
        ("route_key", "route", config.route_max_degree, 0.7),
    ]


def _signal_name_for_column(entity_column: str) -> str:
    mapping = {
        "payment_method": "payment",
        "promotion_code": "promo",
        "pickup_address": "pickup",
        "last_dropoff_address": "dropoff",
        "route_key": "route",
    }
    return mapping.get(entity_column, entity_column)


def _rarity_weight(base_weight: float, degree: int) -> float:
    return base_weight / max(np.log1p(float(degree)), 1.0)


def _entity_gap_days(left: pd.Series, right: pd.Series) -> int:
    left_start = left.get("first_order_date")
    left_end = left.get("last_order_date")
    right_start = right.get("first_order_date")
    right_end = right.get("last_order_date")
    if pd.isna(left_start) or pd.isna(left_end) or pd.isna(right_start) or pd.isna(right_end):
        return 0
    if left_end < right_start:
        return int((right_start - left_end).days)
    if right_end < left_start:
        return int((left_start - right_end).days)
    return 0


def _signal_edges(
    frame: pd.DataFrame,
    entity_column: str,
    signal_name: str,
    max_degree: int,
    base_weight: float,
    max_entity_gap_days: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    distinct = _distinct_pair_entities(frame, entity_column, signal_name)
    if distinct.empty:
        return [], []

    grouped = distinct.groupby(entity_column, dropna=False)
    edges: list[dict[str, object]] = []
    entity_rows: list[dict[str, object]] = []
    for entity_value, entity_pairs in grouped:
        entity_pairs = entity_pairs.sort_values("pair_key").reset_index(drop=True)
        degree = len(entity_pairs)
        eligible = 2 <= degree <= max_degree
        rarity = _rarity_weight(base_weight, degree)
        entity_rows.append(
            {
                "signal_type": signal_name,
                "entity_value": str(entity_value),
                "pair_degree": degree,
                "eligible_for_graph": eligible,
                "rarity_weight": round(float(rarity), 4),
            }
        )
        if not eligible:
            continue
        pair_records = entity_pairs.to_dict("records")
        for left, right in combinations(pair_records, 2):
            gap_days = _entity_gap_days(pd.Series(left), pd.Series(right))
            if gap_days > max_entity_gap_days:
                continue
            temporal_weight = max(0.25, 1 - (gap_days / max(max_entity_gap_days + 1, 1)))
            edges.append(
                {
                    "left": left["pair_key"],
                    "right": right["pair_key"],
                    "signal_type": signal_name,
                    "entity_value": str(entity_value),
                    "entity_degree": degree,
                    "gap_days": gap_days,
                    "edge_weight": float(rarity * temporal_weight),
                }
            )
    return edges, entity_rows


def _build_pair_support_graph(
    candidate_orders: pd.DataFrame,
    pair_keys: pd.DataFrame,
    config: RideGraphSignalConfig,
) -> tuple[nx.Graph, dict[str, set[str]], pd.DataFrame, pd.DataFrame]:
    graph = nx.Graph()
    graph.add_nodes_from(pair_keys["pair_key"].tolist())

    entity_rows: list[dict[str, object]] = []
    edge_candidates: dict[tuple[str, str], dict[str, object]] = {}
    for entity_column, signal_name, max_degree, base_weight in _graph_signal_specs(config):
        signal_edges, signal_entities = _signal_edges(
            candidate_orders,
            entity_column,
            signal_name,
            max_degree,
            base_weight,
            config.max_entity_gap_days,
        )
        entity_rows.extend(signal_entities)
        for edge in signal_edges:
            edge_key = tuple(sorted((str(edge["left"]), str(edge["right"]))))
            aggregated = edge_candidates.setdefault(
                edge_key,
                {
                    "left": edge_key[0],
                    "right": edge_key[1],
                    "total_weight": 0.0,
                    "signal_types": set(),
                    "shared_entities": set(),
                    "max_gap_days": 0,
                },
            )
            aggregated["total_weight"] += float(edge["edge_weight"])
            aggregated["signal_types"].add(str(edge["signal_type"]))
            aggregated["shared_entities"].add(f"{edge['signal_type']}::{edge['entity_value']}")
            aggregated["max_gap_days"] = max(int(aggregated["max_gap_days"]), int(edge["gap_days"]))

    retained_rows: list[dict[str, object]] = []
    support_by_pair: dict[str, set[str]] = {}
    for edge_key, aggregated in edge_candidates.items():
        distinct_signal_count = len(aggregated["signal_types"])
        total_weight = float(aggregated["total_weight"])
        shared_entity_count = len(aggregated["shared_entities"])
        has_multi_signal_support = distinct_signal_count >= config.min_shared_signals and total_weight >= config.min_edge_weight
        has_strong_single_signal = (
            distinct_signal_count >= 1
            and shared_entity_count >= config.single_signal_min_shared_entities
            and total_weight >= config.single_signal_min_weight
        )
        if not has_multi_signal_support and not has_strong_single_signal:
            continue
        graph.add_edge(
            aggregated["left"],
            aggregated["right"],
            weight=round(total_weight, 4),
            signal_types=set(aggregated["signal_types"]),
            shared_entity_count=shared_entity_count,
        )
        retained_rows.append(
            {
                "left": aggregated["left"],
                "right": aggregated["right"],
                "edge_weight": round(total_weight, 4),
                "distinct_signal_count": distinct_signal_count,
                "shared_entity_count": shared_entity_count,
                "max_gap_days": int(aggregated["max_gap_days"]),
                "signal_types": "|".join(sorted(aggregated["signal_types"])),
            }
        )
        for pair_key in edge_key:
            support_by_pair.setdefault(pair_key, set()).update(aggregated["signal_types"])

    entity_report = pd.DataFrame(entity_rows)
    edge_report = pd.DataFrame(retained_rows)
    return graph, support_by_pair, entity_report, edge_report


def build_graph_quality_reports(
    active_orders: pd.DataFrame,
    pair_stats: pd.DataFrame,
    config: RideGraphSignalConfig | None = None,
) -> dict[str, pd.DataFrame]:
    graph_config = config or RideGraphSignalConfig()
    graph_config.validate()
    if pair_stats.empty:
        return {
            "graph_quality": pd.DataFrame(columns=["metric", "value"]),
            "graph_signal_summary": pd.DataFrame(
                columns=[
                    "signal_type",
                    "distinct_entities",
                    "eligible_entities",
                    "filtered_entities",
                    "avg_pair_degree",
                    "max_pair_degree",
                    "avg_rarity_weight",
                    "retained_edge_count",
                ]
            ),
            "graph_entity_degree_report": pd.DataFrame(
                columns=["signal_type", "entity_value", "pair_degree", "eligible_for_graph", "rarity_weight"]
            ),
        }

    pair_keys = _pair_key_frame(pair_stats[["driver_id", "customer_id"]])
    candidate_orders = active_orders.merge(pair_stats[["driver_id", "customer_id"]], on=["driver_id", "customer_id"], how="inner")
    candidate_orders = _pair_key_frame(candidate_orders)
    graph, _, entity_report, edge_report = _build_pair_support_graph(candidate_orders, pair_keys, graph_config)

    component_sizes = [len(component) for component in nx.connected_components(graph)]
    node_count = graph.number_of_nodes()
    linked_pair_counts = [graph.degree(node) for node in graph.nodes]
    largest_component = max(component_sizes, default=0)
    graph_quality = pd.DataFrame(
        [
            {"metric": "candidate_pairs", "value": int(len(pair_stats))},
            {"metric": "graph_nodes", "value": int(node_count)},
            {"metric": "graph_edges", "value": int(graph.number_of_edges())},
            {"metric": "component_count", "value": int(len(component_sizes))},
            {"metric": "largest_component_size", "value": int(largest_component)},
            {
                "metric": "largest_component_share",
                "value": round(float(largest_component / node_count), 4) if node_count else 0.0,
            },
            {"metric": "isolated_pairs", "value": int(sum(1 for degree in linked_pair_counts if degree == 0))},
            {"metric": "avg_linked_pair_count", "value": round(float(np.mean(linked_pair_counts)), 4) if linked_pair_counts else 0.0},
            {"metric": "p90_linked_pair_count", "value": round(float(np.quantile(linked_pair_counts, 0.9)), 4) if linked_pair_counts else 0.0},
        ]
    )

    if entity_report.empty:
        graph_signal_summary = pd.DataFrame(
            columns=[
                "signal_type",
                "distinct_entities",
                "eligible_entities",
                "filtered_entities",
                "avg_pair_degree",
                "max_pair_degree",
                "avg_rarity_weight",
                "retained_edge_count",
            ]
        )
    else:
        retained_signal_counts = (
            edge_report.assign(signal_type=edge_report["signal_types"].str.split("|"))
            .explode("signal_type")
            .groupby("signal_type", dropna=False)
            .size()
            .rename("retained_edge_count")
            .reset_index()
            if not edge_report.empty
            else pd.DataFrame(columns=["signal_type", "retained_edge_count"])
        )
        graph_signal_summary = (
            entity_report.groupby("signal_type", dropna=False)
            .agg(
                distinct_entities=("entity_value", "nunique"),
                eligible_entities=("eligible_for_graph", "sum"),
                filtered_entities=("eligible_for_graph", lambda values: int((~values.astype(bool)).sum())),
                avg_pair_degree=("pair_degree", "mean"),
                max_pair_degree=("pair_degree", "max"),
                avg_rarity_weight=("rarity_weight", "mean"),
            )
            .reset_index()
            .merge(retained_signal_counts, on="signal_type", how="left")
        )
        graph_signal_summary["retained_edge_count"] = graph_signal_summary["retained_edge_count"].fillna(0).astype(int)
        for column in ("avg_pair_degree", "avg_rarity_weight"):
            graph_signal_summary[column] = graph_signal_summary[column].round(4)

    entity_degree_report = (
        entity_report.sort_values(["eligible_for_graph", "pair_degree", "signal_type"], ascending=[False, False, True])
        if not entity_report.empty
        else entity_report
    )
    return {
        "graph_quality": graph_quality,
        "graph_signal_summary": graph_signal_summary,
        "graph_entity_degree_report": entity_degree_report,
    }


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
        result["network_support_score"] = pd.Series(dtype=float)
        result["network_risk_score"] = pd.Series(dtype=float)
        result["fraud_risk_score"] = pd.Series(dtype=float)
        result["business_impact_score"] = pd.Series(dtype=float)
        result["investigation_priority_score"] = pd.Series(dtype=float)
        result["priority_score"] = pd.Series(dtype=float)
        return result

    pair_keys = _pair_key_frame(pair_stats[["driver_id", "customer_id"]])
    candidate_orders = active_orders.merge(pair_stats[["driver_id", "customer_id"]], on=["driver_id", "customer_id"], how="inner")
    candidate_orders = _pair_key_frame(candidate_orders)

    graph, support_by_pair, _, _ = _build_pair_support_graph(candidate_orders, pair_keys, graph_config)

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
        distinct = _distinct_pair_entities(candidate_orders, entity_column, _signal_name_for_column(entity_column))
        if distinct.empty:
            return pd.DataFrame(columns=["pair_key", entity_column])
        grouped = distinct.groupby(entity_column, dropna=False)["pair_key"].transform("nunique")
        filtered = distinct[(grouped >= 2) & (grouped <= max_degree)].copy()
        if filtered.empty:
            return pd.DataFrame(columns=["pair_key", entity_column])
        return filtered.groupby("pair_key", dropna=False)[entity_column].nunique().reset_index()

    payment_counts = count_shared_entities("payment_method", graph_config.payment_max_degree).rename(columns={"payment_method": "shared_payment_count"})
    promo_counts = count_shared_entities("promotion_code", graph_config.promo_max_degree).rename(columns={"promotion_code": "shared_promo_count"})
    pickup_counts = count_shared_entities("pickup_address", graph_config.address_max_degree).rename(columns={"pickup_address": "shared_pickup_count"})
    dropoff_counts = count_shared_entities("last_dropoff_address", graph_config.address_max_degree).rename(columns={"last_dropoff_address": "shared_dropoff_count"})
    route_counts = count_shared_entities("route_key", graph_config.route_max_degree).rename(columns={"route_key": "shared_route_count"})

    enriched = pair_stats.merge(pair_keys, on=["driver_id", "customer_id"], how="left")
    for counts in (payment_counts, promo_counts, pickup_counts, dropoff_counts, route_counts):
        enriched = enriched.merge(counts, on="pair_key", how="left")
    enriched = enriched.merge(components, on="pair_key", how="left")

    if "pair_collusion_score" not in enriched.columns:
        enriched["pair_collusion_score"] = enriched["pair_core_score"]
    if "suspected_ghost_score" not in enriched.columns:
        enriched["suspected_ghost_score"] = 0.0
    if "business_impact_score" not in enriched.columns:
        enriched["business_impact_score"] = 0.0

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

    linked_pair_strength = np.clip(np.log1p(enriched["linked_pair_count"]) / np.log1p(8.0), 0, 1)
    signal_strength = np.clip(enriched["supporting_signal_count"] / 4.0, 0, 1)
    shared_entity_total = (
        enriched["shared_payment_count"]
        + enriched["shared_promo_count"]
        + enriched["shared_pickup_count"]
        + enriched["shared_dropoff_count"]
        + enriched["shared_route_count"]
    )
    shared_entity_strength = np.clip(np.log1p(shared_entity_total) / np.log1p(12.0), 0, 1)
    component_cohesion = np.clip(
        enriched["component_density"] * (4.0 / np.log1p(enriched["component_size"].clip(lower=2))),
        0,
        1,
    )
    network_score = 100 * (
        0.35 * linked_pair_strength
        + 0.30 * signal_strength
        + 0.20 * shared_entity_strength
        + 0.15 * component_cohesion
    )
    enriched["network_support_score"] = network_score.round(2)
    network_alignment = np.clip(
        0.35
        + 0.35 * enriched["pair_collusion_score"].fillna(enriched["pair_core_score"]).div(100.0)
        + 0.30 * enriched["suspected_ghost_score"].fillna(0.0).div(100.0),
        0.35,
        1.0,
    )
    enriched["network_risk_score"] = (enriched["network_support_score"] * network_alignment).round(2)
    enriched["fraud_risk_score"] = (
        0.35 * enriched["pair_collusion_score"].fillna(enriched["pair_core_score"])
        + 0.45 * enriched["suspected_ghost_score"].fillna(0.0)
        + 0.20 * enriched["network_risk_score"].fillna(0.0)
    ).round(2)
    enriched["investigation_priority_score"] = (
        0.75 * enriched["fraud_risk_score"].fillna(0.0)
        + 0.25 * enriched["business_impact_score"].fillna(0.0)
    ).round(2)
    enriched["priority_score"] = enriched["investigation_priority_score"]
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
        "trip_threshold",
        "volume_score",
        "concentration_score",
        "raw_concentration",
        "support_factor",
        "pair_core_score",
        "pair_collusion_score",
        "suspected_ghost_rate",
        "temporal_score",
        "avg_gmv_percentile_by_cohort",
        "low_value_farming_score",
        "suspected_ghost_score",
        "pair_risk_score",
        "network_support_score",
        "network_risk_score",
        "business_impact_score",
        "fraud_risk_score",
        "investigation_priority_score",
        "priority_score",
        "dominant_route_key",
        "dominant_route_share",
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
        "volume_cohort",
        "cohort_trip_threshold",
        "trip_count_percentile",
    ]
    defaults: dict[str, object] = {
        "n_ghost": 0,
        "min_gap_min": pd.NA,
        "ghost_rate": 0.0,
        "high_confidence": False,
        "dominant_route_key": pd.NA,
        "dominant_route_share": 0.0,
        "volume_score": 0.0,
        "concentration_score": 0.0,
        "raw_concentration": 0.0,
        "support_factor": 0.0,
        "pair_core_score": pd.NA,
        "pair_collusion_score": pd.NA,
        "suspected_ghost_rate": 0.0,
        "temporal_score": 0.0,
        "avg_gmv_percentile_by_cohort": 0.0,
        "low_value_farming_score": 0.0,
        "suspected_ghost_score": 0.0,
        "pair_risk_score": 0.0,
        "network_support_score": 0.0,
        "network_risk_score": 0.0,
        "business_impact_score": 0.0,
        "fraud_risk_score": 0.0,
        "investigation_priority_score": pd.NA,
        "priority_score": pd.NA,
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
        "volume_cohort": pd.NA,
        "cohort_trip_threshold": 0.0,
        "trip_count_percentile": 0.0,
    }
    pair_reason_rows = pair_reason_rows.copy()
    for column, value in defaults.items():
        if column not in pair_reason_rows.columns:
            pair_reason_rows[column] = value
    if "investigation_priority_score" in pair_reason_rows.columns:
        pair_reason_rows["investigation_priority_score"] = pair_reason_rows["investigation_priority_score"].fillna(pair_reason_rows["pair_risk_score"])
    if "priority_score" in pair_reason_rows.columns:
        pair_reason_rows["priority_score"] = pair_reason_rows["priority_score"].fillna(pair_reason_rows["investigation_priority_score"])
    if "pair_core_score" in pair_reason_rows.columns:
        pair_reason_rows["pair_core_score"] = pair_reason_rows["pair_core_score"].fillna(0.0)
    if "network_support_score" in pair_reason_rows.columns:
        pair_reason_rows["network_support_score"] = pair_reason_rows["network_support_score"].fillna(0.0)
    if "pair_collusion_score" in pair_reason_rows.columns:
        pair_reason_rows["pair_collusion_score"] = pair_reason_rows["pair_collusion_score"].fillna(pair_reason_rows["pair_core_score"])

    flagged = active_orders.merge(pair_reason_rows[columns], on=["driver_id", "customer_id"], how="inner")
    return flagged.assign(
        domain="ride",
        rule_version="kbc_v2_pair_graph_core",
        risk_tier=np.select(
            [
                flagged["ghost_rate"].ge(0.8) & flagged["n_trips"].ge(10),
                flagged["priority_score"].ge(80),
                flagged["priority_score"].ge(65),
                flagged["priority_score"].ge(50),
            ],
            ["IMMEDIATE_REVIEW", "IMMEDIATE_REVIEW", "HIGH_RISK", "MONITOR"],
            default="LOW_PRIORITY",
        ),
        merchant_id=pd.NA,
        promotion_code=flagged["promotion_code"].fillna(""),
        customer_repeat_ratio=flagged["pair_share_customer"],
        pair_ratio=flagged["pair_share_driver"],
        pair_orders=flagged["n_trips"],
        flagged_at=pd.Timestamp.now(tz="UTC").isoformat(),
        evidence_json=flagged.apply(
            lambda row: {
                "driver_id": row["driver_id"],
                "customer_id": row["customer_id"],
                "n_trips": int(row["n_trips"]),
                "n_ghost": int(row["n_ghost"]),
                "min_gap_min": None if pd.isna(row["min_gap_min"]) else round(float(row["min_gap_min"]), 3),
                "ghost_rate": round(_safe_float(row["ghost_rate"]), 4),
                "pair_share_driver": round(_safe_float(row["pair_share_driver"]), 4),
                "pair_share_customer": round(_safe_float(row["pair_share_customer"]), 4),
                "volume_score": round(_safe_float(row["volume_score"]), 4),
                "raw_concentration": round(_safe_float(row["raw_concentration"]), 4),
                "support_factor": round(_safe_float(row["support_factor"]), 4),
                "concentration_score": round(_safe_float(row["concentration_score"]), 4),
                "pair_core_score": round(_safe_float(row["pair_core_score"]), 2),
                "pair_collusion_score": round(_safe_float(row["pair_collusion_score"]), 2),
                "suspected_ghost_rate": round(_safe_float(row["suspected_ghost_rate"]), 4),
                "temporal_score": round(_safe_float(row["temporal_score"]), 4),
                "low_value_farming_score": round(_safe_float(row["low_value_farming_score"]), 4),
                "suspected_ghost_score": round(_safe_float(row["suspected_ghost_score"]), 2),
                "pair_risk_score": round(_safe_float(row["pair_risk_score"]), 2),
                "network_support_score": round(_safe_float(row["network_support_score"]), 2),
                "network_risk_score": round(_safe_float(row["network_risk_score"]), 2),
                "business_impact_score": round(_safe_float(row["business_impact_score"]), 2),
                "fraud_risk_score": round(_safe_float(row["fraud_risk_score"]), 2),
                "investigation_priority_score": round(_safe_float(row["investigation_priority_score"]), 2),
                "priority_score": round(_safe_float(row["priority_score"]), 2),
                "dominant_route_share": round(_safe_float(row["dominant_route_share"]), 4),
                "high_confidence": bool(row["high_confidence"]),
                "dominant_route_key": row["dominant_route_key"],
                "linked_pair_count": int(row["linked_pair_count"]),
                "supporting_signal_count": int(row["supporting_signal_count"]),
                "component_id": row["component_id"],
                "component_size": int(row["component_size"]),
                "component_density": round(_safe_float(row["component_density"]), 4),
            },
            axis=1,
        ),
    )


def summarize_daily_flags(flagged_orders: pd.DataFrame) -> pd.DataFrame:
    if flagged_orders.empty:
        return pd.DataFrame(columns=["domain", "order_date", "rule_name", "flagged_orders", "flagged_customers", "model_overlap_orders", "total_gmv", "total_discount"])

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
        return pd.DataFrame(columns=["domain", "rule_name", "flagged_orders", "flagged_customers", "avg_priority_score", "avg_network_support_score", "model_overlap_orders", "model_overlap_rate"])
    base = flagged_orders.drop_duplicates(["order_id", "rule_name"]).copy()
    summary = (
        base.groupby(["domain", "rule_name"], dropna=False)
        .agg(
            flagged_orders=("order_id", "nunique"),
            flagged_customers=("customer_id", "nunique"),
            avg_priority_score=("priority_score", "mean"),
            avg_network_support_score=("network_support_score", "mean"),
            avg_pair_risk_score=("pair_risk_score", "mean"),
            avg_ghost_score=("suspected_ghost_score", "mean"),
        )
        .reset_index()
    )
    return summary.assign(model_overlap_orders=0, model_overlap_rate=0.0)


def build_priority_recommendations(flagged_orders: pd.DataFrame) -> pd.DataFrame:
    if flagged_orders.empty:
        return pd.DataFrame(columns=["domain", "rule_name", "priority_score", "recommendation", "flagged_orders", "avg_network_support_score", "model_overlap_rate", "total_discount", "total_gmv"])
    base = flagged_orders.drop_duplicates(["order_id", "rule_name"]).copy()
    summary = (
        base.groupby(["domain", "rule_name"], dropna=False)
        .agg(
            flagged_orders=("order_id", "nunique"),
            total_discount=("discount", "sum"),
            total_gmv=("gmv", "sum"),
            avg_pair_core_score=("pair_core_score", "mean"),
            avg_network_support_score=("network_support_score", "mean"),
            avg_pair_risk_score=("pair_risk_score", "mean"),
            avg_ghost_score=("suspected_ghost_score", "mean"),
            avg_business_impact_score=("business_impact_score", "mean"),
            high_confidence_orders=("high_confidence", "sum"),
        )
        .reset_index()
    )
    summary = summary.assign(
        priority_score=(0.35 * summary["avg_pair_risk_score"] + 0.15 * summary["avg_network_support_score"] + 0.20 * summary["avg_business_impact_score"] + 0.30 * summary["avg_ghost_score"]).round(2),
        recommendation="Prioritize pairs with strong ghost evidence first, then confirm pair concentration and only use the shared-entity network as supporting evidence for coordinated behavior.",
        model_overlap_rate=0.0,
    )
    return summary.sort_values(["priority_score", "flagged_orders"], ascending=False)


def build_component_case_summary(pair_stats: pd.DataFrame) -> pd.DataFrame:
    if pair_stats.empty or "component_id" not in pair_stats.columns:
        return pd.DataFrame(
            columns=[
                "component_id",
                "driver_count",
                "customer_count",
                "pair_count",
                "high_risk_pair_count",
                "high_risk_pair_ratio",
                "average_pair_score",
                "maximum_pair_score",
                "rare_shared_entity_count",
                "weighted_internal_edge_sum",
                "component_density",
                "network_risk_score",
                "component_risk_tier",
            ]
        )

    summary = (
        pair_stats.groupby("component_id", dropna=False)
        .agg(
            driver_count=("driver_id", "nunique"),
            customer_count=("customer_id", "nunique"),
            pair_count=("driver_id", "size"),
            high_risk_pair_count=("priority_score", lambda values: int(pd.Series(values).ge(65).sum())),
            average_pair_score=("fraud_risk_score", "mean"),
            maximum_pair_score=("fraud_risk_score", "max"),
            rare_shared_entity_count=("supporting_signal_count", "sum"),
            weighted_internal_edge_sum=("component_edge_count", "first"),
            component_density=("component_density", "first"),
            network_risk_score=("network_risk_score", "mean"),
        )
        .reset_index()
    )
    summary["high_risk_pair_ratio"] = (
        summary["high_risk_pair_count"].div(summary["pair_count"].replace(0, np.nan)).fillna(0.0).round(4)
    )
    for column in ("average_pair_score", "maximum_pair_score", "network_risk_score", "component_density"):
        summary[column] = summary[column].round(2)
    summary["component_risk_tier"] = np.select(
        [
            summary["network_risk_score"].ge(80),
            summary["network_risk_score"].ge(65),
            summary["network_risk_score"].ge(50),
        ],
        ["IMMEDIATE_REVIEW", "HIGH_RISK", "MONITOR"],
        default="LOW_PRIORITY",
    )
    return summary.sort_values(["network_risk_score", "pair_count"], ascending=False)


def build_pair_evidence(pair_reason_rows: pd.DataFrame) -> pd.DataFrame:
    if pair_reason_rows.empty:
        return pd.DataFrame(
            columns=[
                "pair_id",
                "driver_id",
                "customer_id",
                "evidence_type",
                "observed_value",
                "expected_value",
                "threshold",
                "score_contribution",
                "data_quality_level",
                "description",
            ]
        )

    def observed_value(row: pd.Series) -> object:
        mapping = {
            "KB-C_EXTREME_VOLUME": row.get("n_trips"),
            "KB-C_TIGHT_PAIR_SHARE": row.get("concentration_score"),
            "KB-C_SUSPICIOUS_COMPONENT": row.get("component_size"),
            "KB-C_HIGH_GHOST_RATE": row.get("ghost_rate"),
            "KB-C_SUPERFAST_GAP": row.get("min_gap_min"),
            "KB-C_ROUTE_LOOP": row.get("dominant_route_share"),
        }
        return mapping.get(row.get("reason_code"), pd.NA)

    threshold_value = {
        "KB-C_EXTREME_VOLUME": "cohort_trip_threshold",
        "KB-C_TIGHT_PAIR_SHARE": 0.5,
        "KB-C_SUSPICIOUS_COMPONENT": 2,
        "KB-C_HIGH_GHOST_RATE": 0.3,
        "KB-C_SUPERFAST_GAP": 5.0,
        "KB-C_ROUTE_LOOP": 0.5,
    }
    evidence = pair_reason_rows.copy()
    evidence["pair_id"] = (
        evidence["driver_id"].astype("string").str.strip() + "||" + evidence["customer_id"].astype("string").str.strip()
    )
    evidence["evidence_type"] = evidence["reason_code"]
    evidence["observed_value"] = evidence.apply(observed_value, axis=1)
    evidence["expected_value"] = pd.NA
    evidence["threshold"] = evidence["reason_code"].map(threshold_value).fillna(pd.NA)
    evidence["score_contribution"] = evidence["priority_score"].fillna(evidence["pair_risk_score"]).round(2)
    evidence["data_quality_level"] = "derived"
    evidence["description"] = evidence["flag_reason"]
    return evidence[
        [
            "pair_id",
            "driver_id",
            "customer_id",
            "evidence_type",
            "observed_value",
            "expected_value",
            "threshold",
            "score_contribution",
            "data_quality_level",
            "description",
        ]
    ].drop_duplicates()


def build_quality_report(
    raw_orders: pd.DataFrame | int,
    active_orders: pd.DataFrame | int,
    pair_stats: pd.DataFrame,
    trip_threshold: float,
    flagged_orders: pd.DataFrame,
) -> pd.DataFrame:
    raw_order_count = int(raw_orders if isinstance(raw_orders, int) else len(raw_orders))
    active_order_count = int(active_orders if isinstance(active_orders, int) else len(active_orders))
    rows = [
        {"metric": "raw_orders", "value": raw_order_count},
        {"metric": "active_orders", "value": active_order_count},
        {"metric": "candidate_pairs", "value": int(len(pair_stats))},
        {"metric": "trip_threshold_q9999", "value": float(trip_threshold)},
        {"metric": "flagged_pairs", "value": int(pair_stats[["driver_id", "customer_id"]].drop_duplicates().shape[0])},
        {"metric": "flagged_rows", "value": int(len(flagged_orders))},
        {"metric": "high_confidence_pairs", "value": int(pair_stats["high_confidence"].sum()) if "high_confidence" in pair_stats.columns and not pair_stats.empty else 0},
    ]
    return pd.DataFrame(rows)


def evaluate_known_pairs(flagged_orders: pd.DataFrame, known_pairs: pd.DataFrame) -> pd.DataFrame:
    if flagged_orders.empty or known_pairs.empty:
        return pd.DataFrame()

    pair_hits = flagged_orders[
        [
            "driver_id",
            "customer_id",
            "reason_code",
            "high_confidence",
            "n_trips",
            "ghost_rate",
            "min_gap_min",
            "pair_core_score",
            "priority_score",
        ]
    ].drop_duplicates()
    evaluation = known_pairs.merge(pair_hits, on=["driver_id", "customer_id"], how="left")
    return evaluation.assign(is_flagged=evaluation["reason_code"].notna())
