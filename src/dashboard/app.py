"""Shared KB-C dashboard helpers plus the default dashboard entrypoint."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st


REPORT_DIR = Path("reports/task3")

RULE_DISPLAY_NAMES = {
    "REPEATED_CUSTOMER_DRIVER": "Danh sach cap tai xe - khach hang can xem",
}


def add_rule_display(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or "rule_name" not in frame.columns:
        return frame
    result = frame.copy()
    result["rule_display_name"] = result["rule_name"].map(RULE_DISPLAY_NAMES).fillna(result["rule_name"])
    return result


@st.cache_data(show_spinner=False)
def read_reports(report_dir: str) -> dict[str, pd.DataFrame]:
    root = Path(report_dir)
    reports: dict[str, pd.DataFrame] = {}
    for name, filename in {
        "daily": "daily_rule_summary.csv",
        "comparison": "rule_model_comparison.csv",
        "recommendations": "priority_recommendations.csv",
        "quality": "quality_report.csv",
        "graph_quality": "graph_quality_report.csv",
        "graph_signal_summary": "graph_signal_summary.csv",
        "pair_evidence": "pair_evidence.csv",
        "flags": "flagged_orders.parquet",
        "kbc_pairs": "kbc_pair_summary.csv",
        "kbc_reasons": "kbc_pair_reasons.csv",
        "kbc_known": "known_case_evaluation.csv",
        "kbc_components": "suspicious_components.csv",
    }.items():
        path = root / filename
        if not path.exists():
            reports[name] = pd.DataFrame()
        elif path.suffix == ".parquet":
            reports[name] = pd.read_parquet(path)
        else:
            reports[name] = pd.read_csv(path)
    return reports


def build_kbc_reason_pair_summary(kbc_reasons: pd.DataFrame) -> pd.DataFrame:
    if kbc_reasons.empty or "reason_code" not in kbc_reasons.columns:
        return pd.DataFrame()
    return (
        kbc_reasons.groupby("reason_code", dropna=False)
        .agg(
            flagged_pairs=("driver_id", "size"),
            high_confidence_pairs=("high_confidence", "sum"),
            avg_n_trips=("n_trips", "mean"),
            avg_ghost_rate=("ghost_rate", "mean"),
            min_gap_min=("min_gap_min", "min"),
        )
        .reset_index()
        .sort_values(["flagged_pairs", "high_confidence_pairs"], ascending=False)
    )


def build_kbc_daily_summary(daily: pd.DataFrame) -> pd.DataFrame:
    if daily.empty or "rule_name" not in daily.columns:
        return pd.DataFrame()
    return daily[daily["rule_name"] == "REPEATED_CUSTOMER_DRIVER"].copy()


def build_kbc_metric_guide() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "metric": "pair_core_score",
                "meaning": "Diem cot loi cua cap tai xe - khach hang, duoc tinh tu muc do lap lai va muc do tap trung.",
            },
            {
                "metric": "pair_risk_score",
                "meaning": "Diem rui ro cua chinh cap, da cong them ghost evidence va temporal pattern.",
            },
            {
                "metric": "suspected_ghost_score",
                "meaning": "Diem nghieng ve ghost-trip, ket hop zero-speed rate, temporal signal va low-value farming.",
            },
            {
                "metric": "network_support_score",
                "meaning": "Diem bo sung cho biet cap nay co duoc nhom lien ket xung quanh cung co them hay khong.",
            },
            {
                "metric": "priority_score",
                "meaning": "Diem sap thu tu xem truoc, di tu bang chung o chinh cap roi moi cong them thong tin nhom lien ket.",
            },
            {
                "metric": "business_impact_score",
                "meaning": "Diem tac dong van hanh/kinh doanh dua tren GMV, discount va tan suat lap lai.",
            },
            {
                "metric": "component_size",
                "meaning": "So cap dang chu y nam chung trong mot nhom lien ket.",
            },
            {
                "metric": "linked_pair_count",
                "meaning": "So cap dang chu y noi truc tiep voi cap hien tai qua dia chi, thanh toan, khuyen mai hoac tuyen duong dung chung.",
            },
        ]
    )


def build_window_metrics(flags: pd.DataFrame) -> pd.DataFrame:
    if flags.empty or "order_date" not in flags.columns:
        return pd.DataFrame()
    frame = flags.copy()
    frame = frame.assign(order_date=pd.to_datetime(frame["order_date"], errors="coerce").dt.date)
    latest_date = max(date for date in frame["order_date"].dropna())
    rows: list[dict[str, object]] = []
    for days in (1, 7, 30):
        start_date = (pd.Timestamp(latest_date) - pd.Timedelta(days=days - 1)).date()
        window = frame[frame["order_date"] >= start_date].copy()
        rows.append(
            {
                "window_label": f"{days}D",
                "days": days,
                "flagged_orders": int(window["order_id"].nunique()) if "order_id" in window.columns else 0,
                "flagged_pairs": int(window[["driver_id", "customer_id"]].drop_duplicates().shape[0]) if {"driver_id", "customer_id"} <= set(window.columns) else 0,
                "flagged_customers": int(window["customer_id"].nunique()) if "customer_id" in window.columns else 0,
                "flagged_drivers": int(window["driver_id"].nunique()) if "driver_id" in window.columns else 0,
                "high_conf_orders": int(window.loc[window["high_confidence"].fillna(False), "order_id"].nunique()) if {"high_confidence", "order_id"} <= set(window.columns) else 0,
                "high_risk_orders": int(window.loc[window["risk_tier"].isin(["IMMEDIATE_REVIEW", "HIGH_RISK", "HIGH"]), "order_id"].nunique()) if {"risk_tier", "order_id"} <= set(window.columns) else 0,
                "medium_risk_orders": int(window.loc[window["risk_tier"].isin(["MONITOR", "MEDIUM"]), "order_id"].nunique()) if {"risk_tier", "order_id"} <= set(window.columns) else 0,
                "watchlist_orders": int(window.loc[window["risk_tier"].isin(["LOW_PRIORITY", "WATCHLIST"]), "order_id"].nunique()) if {"risk_tier", "order_id"} <= set(window.columns) else 0,
                "start_date": start_date,
                "end_date": latest_date,
            }
        )
    return pd.DataFrame(rows)


def build_entity_summary(flags: pd.DataFrame, entity_col: str) -> pd.DataFrame:
    if flags.empty or entity_col not in flags.columns:
        return pd.DataFrame()
    agg_map: dict[str, tuple[str, str]] = {
        "flagged_orders": ("order_id", "nunique"),
        "high_conf_orders": ("high_confidence", "sum"),
        "avg_priority_score": ("priority_score", "mean"),
        "max_n_trips": ("n_trips", "max"),
        "max_ghost_rate": ("ghost_rate", "max"),
        "min_gap_min": ("min_gap_min", "min"),
    }
    if "network_support_score" in flags.columns:
        agg_map["avg_network_support_score"] = ("network_support_score", "mean")
    if "priority_score" in flags.columns:
        agg_map["max_priority_score"] = ("priority_score", "max")
    if "component_size" in flags.columns:
        agg_map["max_component_size"] = ("component_size", "max")
    if "linked_pair_count" in flags.columns:
        agg_map["max_linked_pair_count"] = ("linked_pair_count", "max")
    if entity_col == "customer_id" and "driver_id" in flags.columns:
        agg_map["linked_drivers"] = ("driver_id", "nunique")
    if entity_col == "driver_id" and "customer_id" in flags.columns:
        agg_map["linked_customers"] = ("customer_id", "nunique")
    return (
        flags.groupby(entity_col, dropna=False)
        .agg(**agg_map)
        .reset_index()
        .sort_values(["flagged_orders", "high_conf_orders", "avg_priority_score"], ascending=False)
    )


def build_rule_cluster_summary(rule_flags: pd.DataFrame, selected_rule: str) -> pd.DataFrame:
    if rule_flags.empty or selected_rule != "REPEATED_CUSTOMER_DRIVER":
        return pd.DataFrame()
    agg_map = {
        "flagged_orders": ("order_id", "nunique"),
        "max_n_trips": ("n_trips", "max"),
        "max_n_ghost": ("n_ghost", "max"),
        "min_gap_min": ("min_gap_min", "min"),
        "max_ghost_rate": ("ghost_rate", "max"),
        "high_confidence": ("high_confidence", "max"),
        "avg_gmv": ("avg_gmv", "mean"),
        "avg_pair_core_score": ("pair_core_score", "mean"),
        "avg_network_support_score": ("network_support_score", "mean"),
        "max_priority_score": ("priority_score", "max"),
        "max_supporting_signal_count": ("supporting_signal_count", "max"),
        "max_linked_pair_count": ("linked_pair_count", "max"),
        "max_component_size": ("component_size", "max"),
        "top_risk_tier": ("risk_tier", "max"),
    }
    return (
        rule_flags.groupby(["customer_id", "driver_id"], dropna=False)
        .agg(**agg_map)
        .reset_index()
        .sort_values(["max_priority_score", "flagged_orders", "max_n_trips"], ascending=False)
    )


def build_neo4j_query_pack(selected_rule: str, row: pd.Series) -> dict[str, str]:
    if selected_rule != "REPEATED_CUSTOMER_DRIVER":
        return {}
    order_id = repr(str(row.get("order_id", "")))
    customer_id = repr(str(row.get("customer_id", "")))
    driver_id = repr(str(row.get("driver_id", "")))
    return {
        "Customer-driver repetition": f"""MATCH (c:Customer {{customer_id: {customer_id}}})-[:PLACED]->(o:Order)<-[:SERVED]-(d:Driver {{driver_id: {driver_id}}})
OPTIONAL MATCH (o)-[:PICKUP_AT]->(pickup:Address)
OPTIONAL MATCH (o)-[:DROPOFF_AT]->(drop:Address)
RETURN c, d, o, pickup, drop
ORDER BY o.order_time DESC
LIMIT 200;""",
        "Selected order details": f"""MATCH (o:Order {{order_id: {order_id}}})
OPTIONAL MATCH (o)<-[:PLACED]-(c:Customer)
OPTIONAL MATCH (o)<-[:SERVED]-(d:Driver)
OPTIONAL MATCH (o)-[:PICKUP_AT]->(pickup:Address)
OPTIONAL MATCH (o)-[:DROPOFF_AT]->(drop:Address)
OPTIONAL MATCH (o)-[:PAID_BY]->(pm:PaymentMethod)
OPTIONAL MATCH (o)-[:USED_PROMO]->(p:PromotionCode)
RETURN o, c, d, pickup, drop, pm, p;""",
        "Customer timeline and linked drivers": f"""MATCH (c:Customer {{customer_id: {customer_id}}})-[:PLACED]->(o:Order)
OPTIONAL MATCH (o)<-[:SERVED]-(d:Driver)
RETURN c, o, d
ORDER BY o.order_time DESC
LIMIT 200;""",
        "Driver timeline and linked customers": f"""MATCH (d:Driver {{driver_id: {driver_id}}})-[:SERVED]->(o:Order)
OPTIONAL MATCH (o)<-[:PLACED]-(c:Customer)
RETURN d, o, c
ORDER BY o.order_time DESC
LIMIT 200;""",
        "Pair route and time reuse": f"""MATCH (c:Customer {{customer_id: {customer_id}}})-[:PLACED]->(o:Order)<-[:SERVED]-(d:Driver {{driver_id: {driver_id}}})
OPTIONAL MATCH (o)-[:PICKUP_AT]->(pickup:Address)
OPTIONAL MATCH (o)-[:DROPOFF_AT]->(drop:Address)
RETURN o.order_id AS order_id, o.order_time AS order_time, pickup.address AS pickup_address, drop.address AS dropoff_address
ORDER BY o.order_time DESC
LIMIT 200;""",
    }


def main() -> None:
    from src.dashboard.kbc_daily_dashboard import render_dashboard

    render_dashboard()


if __name__ == "__main__":
    main()
