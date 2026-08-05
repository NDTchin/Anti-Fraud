"""Task 3 dashboard for daily rule/model and graph-case review."""

from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd
import plotly.express as px
import streamlit as st

from src.config.settings import settings


REPORT_DIR = Path("reports/task3")

RULE_DISPLAY_NAMES = {
    "PROMO_ENTITY_CONCENTRATION": "Promo Abuse Cluster",
    "IMPOSSIBLE_TRAVEL": "Impossible Travel",
    "FIXED_VALUE_PATTERN": "Fixed Basket Pattern",
    "MULTI_LINK_DRIVER": "Linked Driver Network",
    "HIGH_DISCOUNT_OUTLIER": "Extreme Discount Abuse",
    "FOOD_FULFILLMENT_TIME_OUTLIER": "Fulfillment Time Anomaly",
    "REPEATED_CUSTOMER_DRIVER": "KB-C Superfast Driver-Customer Duo",
    "SERVICE_TRIP_OUTLIER": "Ride Trip Anomaly",
}


def add_rule_display(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or "rule_name" not in frame.columns:
        return frame
    result = frame.copy()
    result["rule_display_name"] = result["rule_name"].map(RULE_DISPLAY_NAMES).fillna(result["rule_name"])
    return result


def rule_option_labels(rule_names: list[str]) -> dict[str, str]:
    return {rule_name: f"{RULE_DISPLAY_NAMES.get(rule_name, rule_name)} ({rule_name})" for rule_name in rule_names}


@st.cache_data(show_spinner=False)
def read_reports(report_dir: str) -> dict[str, pd.DataFrame]:
    root = Path(report_dir)
    reports: dict[str, pd.DataFrame] = {}
    for name, filename in {
        "daily": "daily_rule_summary.csv",
        "comparison": "rule_model_comparison.csv",
        "recommendations": "priority_recommendations.csv",
        "quality": "quality_report.csv",
        "flags": "flagged_orders.parquet",
        "anomalies": "anomaly_scores.parquet",
        "kbc_pairs": "kbc_pair_summary.csv",
        "kbc_reasons": "kbc_pair_reasons.csv",
        "kbc_known": "known_case_evaluation.csv",
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
                "metric": "Flagged pairs",
                "meaning": "So cap tai xe-khach hang bi rule KB-C giu lai sau khi ap nguong va bo loc hien tai.",
            },
            {
                "metric": "High-confidence pairs",
                "meaning": "So cap co dau hieu manh hon, tuc `ghost_rate > 0.3` hoac `min_gap_min < 5`.",
            },
            {
                "metric": "Risk tier",
                "meaning": "Muc uu tien hien tai cua cap theo score cuoi cung: `HIGH`, `MEDIUM`, `WATCHLIST`.",
            },
            {
                "metric": "Flagged orders",
                "meaning": "So order thuoc cac cap dang bi flag. Chi so nay cho biet khoi luong order can review.",
            },
            {
                "metric": "Min gap",
                "meaning": "Khoang cach phut nho nhat giua hai order lien tiep cua cung mot cap. Cang nho cang bat thuong.",
            },
            {
                "metric": "Max ghost rate",
                "meaning": "Ty le lon nhat cua cac order co `avg_kmh = 0` trong cac cap dang duoc hien thi.",
            },
            {
                "metric": "n_trips",
                "meaning": "Tong so chuyen giua mot `driver_id` va `customer_id` trong cua so 4 ngay.",
            },
            {
                "metric": "ghost_rate",
                "meaning": "Ty le chuyen co `avg_kmh = 0` tren tong so chuyen cua cung cap.",
            },
            {
                "metric": "min_gap_min",
                "meaning": "Khoang cach nho nhat giua hai chuyen lien tiep cua cung cap, tinh theo phut.",
            },
            {
                "metric": "rule_score_base",
                "meaning": "Diem rule nen truoc khi cong them ngu canh graph. Day la phan diem den tu hanh vi truc tiep cua pair.",
            },
            {
                "metric": "graph_risk_score",
                "meaning": "Diem bo sung tu graph hien tai: pair nay dinh voi bao nhieu pair dang ngo khac va co bao nhieu tin hieu chia se.",
            },
            {
                "metric": "final_risk_score",
                "meaning": "Diem uu tien review cuoi cung sau khi ket hop score nen va score graph. Trong output hien tai `rule_score` bam theo diem cuoi nay.",
            },
            {
                "metric": "component_size",
                "meaning": "So pair nam trong cung connected component nghi ngo voi pair dang xet.",
            },
            {
                "metric": "linked_pair_count",
                "meaning": "So pair dang ngo khac duoc noi truc tiep voi pair hien tai qua tin hieu chia se.",
            },
        ]
    )


def build_window_metrics(flags: pd.DataFrame) -> pd.DataFrame:
    if flags.empty or "order_date" not in flags.columns:
        return pd.DataFrame()
    frame = flags.copy()
    frame["order_date"] = pd.to_datetime(frame["order_date"], errors="coerce").dt.date
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
                "high_risk_orders": int(window.loc[window["risk_tier"].eq("HIGH"), "order_id"].nunique()) if {"risk_tier", "order_id"} <= set(window.columns) else 0,
                "medium_risk_orders": int(window.loc[window["risk_tier"].eq("MEDIUM"), "order_id"].nunique()) if {"risk_tier", "order_id"} <= set(window.columns) else 0,
                "watchlist_orders": int(window.loc[window["risk_tier"].eq("WATCHLIST"), "order_id"].nunique()) if {"risk_tier", "order_id"} <= set(window.columns) else 0,
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
        "avg_rule_score": ("rule_score", "mean"),
        "max_n_trips": ("n_trips", "max"),
        "max_ghost_rate": ("ghost_rate", "max"),
        "min_gap_min": ("min_gap_min", "min"),
    }
    if "graph_risk_score" in flags.columns:
        agg_map["avg_graph_risk_score"] = ("graph_risk_score", "mean")
    if "final_risk_score" in flags.columns:
        agg_map["max_final_risk_score"] = ("final_risk_score", "max")
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
        .sort_values(["flagged_orders", "high_conf_orders", "avg_rule_score"], ascending=False)
    )


def build_order_reason_summary(flags: pd.DataFrame) -> pd.DataFrame:
    if flags.empty:
        return pd.DataFrame()
    agg_map: dict[str, tuple[str, str]] = {
        "flagged_orders": ("order_id", "nunique"),
        "flagged_pairs": ("driver_id", "nunique"),
        "avg_rule_score": ("rule_score", "mean"),
    }
    if "graph_risk_score" in flags.columns:
        agg_map["avg_graph_risk_score"] = ("graph_risk_score", "mean")
    if "final_risk_score" in flags.columns:
        agg_map["avg_final_risk_score"] = ("final_risk_score", "mean")
    return (
        flags.groupby("reason_code", dropna=False)
        .agg(**agg_map)
        .reset_index()
        .sort_values(["flagged_orders", "avg_rule_score"], ascending=False)
    )


def build_rule_review_context(selected_rule: str) -> pd.DataFrame:
    contexts = {
        "PROMO_ENTITY_CONCENTRATION": {
            "fraud_behavior": "Many customers reuse one promotion around the same merchant with shared payment, address, or driver signals.",
            "analyst_readability": "Analyst can quickly read merchant share, shared signals, and repeated customer usage.",
            "false_positive_risk": "Large legitimate campaigns can look similar if they are not well distributed.",
            "neo4j_drilldown": "Start from PromotionCode, Merchant, PaymentMethod, Address, Driver, and linked customers.",
        },
        "IMPOSSIBLE_TRAVEL": {
            "fraud_behavior": "A customer places consecutive orders from different provinces within an implausibly short time gap.",
            "analyst_readability": "Analyst should read the province pair, event times, and repeat count immediately.",
            "false_positive_risk": "Timestamp quality issues or marketplace routing quirks can create false hops.",
            "neo4j_drilldown": "Start from the customer timeline, then compare the two neighboring orders and provinces.",
        },
        "FIXED_VALUE_PATTERN": {
            "fraud_behavior": "A customer-merchant pair repeats near-identical basket values, which is common in scripted farming.",
            "analyst_readability": "Analyst should read order count, coefficient of variation, and repeated basket value.",
            "false_positive_risk": "Some merchants have rigid combo pricing, so fixed menu bundles can look suspicious.",
            "neo4j_drilldown": "Start from Customer, Merchant, repeated Orders, then inspect Promo and Driver reuse.",
        },
        "MULTI_LINK_DRIVER": {
            "fraud_behavior": "One driver serves multiple suspicious fixed-value customer-merchant pairs and becomes a linkage point.",
            "analyst_readability": "Analyst should read linked pair count and total related discount first.",
            "false_positive_risk": "A very active driver can touch multiple risky pairs by coincidence in dense areas.",
            "neo4j_drilldown": "Start from Driver, then fan out to suspicious Customer-Merchant pairs and related orders.",
        },
        "HIGH_DISCOUNT_OUTLIER": {
            "fraud_behavior": "The discount is extreme for the service and day, suggesting leakage or subsidy capture.",
            "analyst_readability": "Analyst should read discount rate, merchant, promo, and peer orders.",
            "false_positive_risk": "Flash sale and merchant-funded campaigns can look similar.",
            "neo4j_drilldown": "Start from Order, Merchant, PromotionCode, and nearby customer cluster if any.",
        },
        "FOOD_FULFILLMENT_TIME_OUTLIER": {
            "fraud_behavior": "The order is a severe fulfillment-time outlier. This is operational evidence first, not standalone fraud proof.",
            "analyst_readability": "Analyst should read lead time and whether promo is involved, then look for linked suspicious entities.",
            "false_positive_risk": "Operational delays, bad logs, or merchant issues are common false positives.",
            "neo4j_drilldown": "Start from order timeline, then inspect merchant, driver, and related repeated patterns.",
        },
        "REPEATED_CUSTOMER_DRIVER": {
            "fraud_behavior": "A driver-customer pair completes an extreme number of trips in four days, often with ghost rides (avg_kmh = 0) or near-zero turnaround between consecutive trips.",
            "analyst_readability": "Analyst should read n_trips, min_gap_min, ghost_rate, and the high_confidence marker immediately.",
            "false_positive_risk": "Airport shuttles, contracted routes, or dense local loops can create repeated pairs without fraud if ghost rides and ultra-short gaps are absent.",
            "neo4j_drilldown": "Start from the Driver-Customer pair, then inspect consecutive Orders, trip timestamps, Merchant or pickup/dropoff reuse, and zero-speed ride evidence.",
        },
    }
    context = contexts.get(
        selected_rule,
        {
            "fraud_behavior": "This rule captures a risk pattern that still needs supporting evidence.",
            "analyst_readability": "Analyst should read reason code, score, and linked entities quickly.",
            "false_positive_risk": "Business workflows may mimic this pattern, so raw data review is still required.",
            "neo4j_drilldown": "Start from the flagged order or customer, then inspect neighboring entities.",
        },
    )
    return pd.DataFrame(
        [
            {"question": "What fraud behavior does this rule target?", "answer": context["fraud_behavior"]},
            {"question": "Can an analyst read the reason quickly?", "answer": context["analyst_readability"]},
            {"question": "What is the biggest false-positive risk?", "answer": context["false_positive_risk"]},
            {"question": "Where should Neo4j drill-down start?", "answer": context["neo4j_drilldown"]},
        ]
    )


def build_rule_cluster_summary(rule_flags: pd.DataFrame, selected_rule: str) -> pd.DataFrame:
    if rule_flags.empty:
        return pd.DataFrame()

    if selected_rule == "PROMO_ENTITY_CONCENTRATION":
        group_cols = [column for column in ("merchant_id", "promotion_code", "reason_code") if column in rule_flags.columns]
        summary = rule_flags.groupby(group_cols, dropna=False).agg(
            flagged_orders=("order_id", "nunique"),
            flagged_customers=("customer_id", "nunique"),
            avg_rule_score=("rule_score", "mean"),
            max_shared_signal_count=("shared_signal_count", "max"),
            avg_payment_share=("payment_share", "mean"),
            avg_dropoff_share=("dropoff_share", "mean"),
            avg_driver_share=("driver_share", "mean"),
            avg_merchant_order_share=("merchant_order_share", "mean"),
        ).reset_index()
        return summary.sort_values(["flagged_orders", "avg_rule_score"], ascending=False)

    if selected_rule == "IMPOSSIBLE_TRAVEL":
        group_cols = [column for column in ("customer_id", "province_pair", "reason_code") if column in rule_flags.columns]
        summary = rule_flags.groupby(group_cols, dropna=False).agg(
            flagged_orders=("order_id", "nunique"),
            avg_rule_score=("rule_score", "mean"),
            max_impossible_travel_count=("impossible_travel_count", "max"),
            min_time_gap_hours=("time_gap_hours", "min"),
        ).reset_index()
        return summary.sort_values(["max_impossible_travel_count", "flagged_orders", "avg_rule_score"], ascending=False)

    if selected_rule == "FIXED_VALUE_PATTERN":
        group_cols = [column for column in ("customer_id", "merchant_id", "reason_code") if column in rule_flags.columns]
        agg_map = {
            "flagged_orders": ("order_id", "nunique"),
            "avg_rule_score": ("rule_score", "mean"),
            "max_fixed_value_order_count": ("fixed_value_order_count", "max"),
            "min_fixed_value_cv": ("fixed_value_cv", "min"),
            "avg_order_amount_value": ("order_amount_value", "mean"),
        }
        if "risk_tier" in rule_flags.columns:
            agg_map["top_risk_tier"] = ("risk_tier", "max")
        if "supporting_signal" in rule_flags.columns:
            agg_map["supporting_signals"] = ("supporting_signal", lambda values: " | ".join(sorted({str(v) for v in values.dropna() if str(v).strip()})))
        summary = rule_flags.groupby(group_cols, dropna=False).agg(**agg_map).reset_index()
        return summary.sort_values(["max_fixed_value_order_count", "flagged_orders", "avg_rule_score"], ascending=False)

    if selected_rule == "MULTI_LINK_DRIVER":
        group_cols = [column for column in ("driver_id", "reason_code") if column in rule_flags.columns]
        summary = rule_flags.groupby(group_cols, dropna=False).agg(
            flagged_orders=("order_id", "nunique"),
            flagged_customers=("customer_id", "nunique"),
            avg_rule_score=("rule_score", "mean"),
            max_linked_pair_count=("linked_pair_count", "max"),
            max_linked_discount_total=("linked_discount_total", "max"),
        ).reset_index()
        return summary.sort_values(["max_linked_pair_count", "flagged_orders", "avg_rule_score"], ascending=False)

    if selected_rule == "HIGH_DISCOUNT_OUTLIER":
        group_cols = [column for column in ("merchant_id", "promotion_code", "reason_code") if column in rule_flags.columns]
        summary = rule_flags.groupby(group_cols, dropna=False).agg(
            flagged_orders=("order_id", "nunique"),
            flagged_customers=("customer_id", "nunique"),
            avg_rule_score=("rule_score", "mean"),
            avg_discount_rate=("discount_rate", "mean"),
            max_discount_rate=("discount_rate", "max"),
        ).reset_index()
        return summary.sort_values(["flagged_orders", "avg_discount_rate"], ascending=False)

    if selected_rule == "FOOD_FULFILLMENT_TIME_OUTLIER":
        group_cols = [column for column in ("merchant_id", "reason_code") if column in rule_flags.columns]
        summary = rule_flags.groupby(group_cols, dropna=False).agg(
            flagged_orders=("order_id", "nunique"),
            flagged_customers=("customer_id", "nunique"),
            avg_rule_score=("rule_score", "mean"),
            avg_lead_time_second=("lead_time_second", "mean"),
            max_lead_time_second=("lead_time_second", "max"),
        ).reset_index()
        return summary.sort_values(["flagged_orders", "avg_lead_time_second"], ascending=False)

    if selected_rule == "REPEATED_CUSTOMER_DRIVER":
        group_cols = [column for column in ("customer_id", "driver_id", "reason_code") if column in rule_flags.columns]
        agg_map: dict[str, tuple[str, str]] = {
            "flagged_orders": ("order_id", "nunique"),
            "avg_rule_score": ("rule_score", "mean"),
        }
        if "n_trips" in rule_flags.columns:
            agg_map["max_n_trips"] = ("n_trips", "max")
        elif "pair_orders" in rule_flags.columns:
            agg_map["max_pair_orders"] = ("pair_orders", "max")
        if "pair_ratio" in rule_flags.columns:
            agg_map["max_pair_ratio"] = ("pair_ratio", "max")
        if "n_ghost" in rule_flags.columns:
            agg_map["max_n_ghost"] = ("n_ghost", "max")
        if "min_gap_min" in rule_flags.columns:
            agg_map["min_gap_min"] = ("min_gap_min", "min")
        if "ghost_rate" in rule_flags.columns:
            agg_map["max_ghost_rate"] = ("ghost_rate", "max")
        if "high_confidence" in rule_flags.columns:
            agg_map["high_confidence"] = ("high_confidence", "max")
        if "avg_gmv" in rule_flags.columns:
            agg_map["avg_gmv"] = ("avg_gmv", "mean")
        elif "gmv" in rule_flags.columns:
            agg_map["avg_gmv"] = ("gmv", "mean")
        if "rule_score_base" in rule_flags.columns:
            agg_map["avg_rule_score_base"] = ("rule_score_base", "mean")
        if "graph_risk_score" in rule_flags.columns:
            agg_map["avg_graph_risk_score"] = ("graph_risk_score", "mean")
        if "final_risk_score" in rule_flags.columns:
            agg_map["max_final_risk_score"] = ("final_risk_score", "max")
        if "supporting_signal_count" in rule_flags.columns:
            agg_map["max_supporting_signal_count"] = ("supporting_signal_count", "max")
        if "linked_pair_count" in rule_flags.columns:
            agg_map["max_linked_pair_count"] = ("linked_pair_count", "max")
        if "component_size" in rule_flags.columns:
            agg_map["max_component_size"] = ("component_size", "max")
        if "component_density" in rule_flags.columns:
            agg_map["max_component_density"] = ("component_density", "max")
        if "risk_tier" in rule_flags.columns:
            agg_map["top_risk_tier"] = (
                "risk_tier",
                lambda values: next(
                    (
                        tier
                        for tier in ("HIGH", "MEDIUM", "WATCHLIST")
                        if tier in {str(value) for value in values.dropna()}
                    ),
                    None,
                ),
            )
        summary = rule_flags.groupby(group_cols, dropna=False).agg(**agg_map).reset_index()
        sort_cols = [
            column
            for column in (
                "high_confidence",
                "max_final_risk_score",
                "max_n_trips",
                "flagged_orders",
                "avg_rule_score",
            )
            if column in summary.columns
        ]
        if not sort_cols:
            sort_cols = ["flagged_orders", "avg_rule_score"]
        return summary.sort_values(sort_cols, ascending=[False] * len(sort_cols))

    summary = rule_flags.groupby(["reason_code"], dropna=False).agg(
        flagged_orders=("order_id", "nunique"),
        flagged_customers=("customer_id", "nunique"),
        avg_rule_score=("rule_score", "mean"),
    ).reset_index()
    return summary.sort_values(["flagged_orders", "avg_rule_score"], ascending=False)


def build_reason_breakdown(rule_flags: pd.DataFrame) -> pd.DataFrame:
    if rule_flags.empty or "reason_code" not in rule_flags.columns:
        return pd.DataFrame()
    summary = rule_flags.groupby(["reason_code"], dropna=False).agg(
        flagged_orders=("order_id", "nunique"),
        flagged_customers=("customer_id", "nunique"),
        avg_rule_score=("rule_score", "mean"),
    ).reset_index()
    return summary.sort_values(["flagged_orders", "avg_rule_score"], ascending=False)


def build_browser_checklist(selected_rule: str) -> pd.DataFrame:
    checklists = {
        "PROMO_ENTITY_CONCENTRATION": [
            "Check whether the same payment, dropoff, or driver is reused across the promo cluster.",
            "Check whether the promo is naturally spread across many merchants or concentrated in one place.",
            "If the cluster is dense but entity reuse is weak, treat it as possible legitimate campaign traffic.",
        ],
        "IMPOSSIBLE_TRAVEL": [
            "Check the two neighboring orders and confirm the province switch really happens within under 4 hours.",
            "Check whether timestamps look reliable and in the expected local timezone.",
            "If the timeline is clean, this is strong behavioral evidence for shared-account abuse.",
        ],
        "FIXED_VALUE_PATTERN": [
            "Check whether the basket value is nearly identical across repeated orders from the same merchant.",
            "Check whether promo usage, address, or driver reuse also appears around the pair.",
            "If the merchant only sells rigid bundles, lower the fraud confidence.",
        ],
        "MULTI_LINK_DRIVER": [
            "Check how many distinct suspicious customer-merchant pairs the driver touches.",
            "Check whether the same driver appears with repeated promo or address patterns.",
            "If the driver is only generally high-volume with weak supporting links, keep manual review open.",
        ],
        "HIGH_DISCOUNT_OUTLIER": [
            "Check whether the discount level is extreme relative to peer orders for that day and service.",
            "Check whether the order also sits inside a suspicious customer or promo cluster.",
            "If it looks like a flash sale or merchant-funded campaign, reduce fraud confidence.",
        ],
        "FOOD_FULFILLMENT_TIME_OUTLIER": [
            "Check timeline events to see whether the lead time is real or a logging issue.",
            "Check whether merchant, driver, or customer also appears in other suspicious patterns.",
            "Do not conclude fraud from this rule alone if there is no supporting linkage evidence.",
        ],
        "REPEATED_CUSTOMER_DRIVER": [
            "Check whether the pair exceeds the extreme trip-count threshold for the four-day window, for example above the 0.9999 quantile at roughly 12 trips.",
            "Check whether ghost_rate is elevated or whether two consecutive trips happen under 5 minutes apart, especially near 1 minute or less.",
            "If the pair repeats often but has clean speed logs and realistic gaps, keep a legitimate-routing explanation open.",
        ],
    }
    rows = [{"check": item} for item in checklists.get(selected_rule, [
        "Check whether the central entity truly links many suspicious orders or customers.",
        "Validate against raw data before concluding fraud.",
    ])]
    return pd.DataFrame(rows)


def quote_cypher_value(value: object) -> str:
    if value is None or pd.isna(value):
        return "''"
    text = str(value).replace("'", "\'")
    return f"'{text}'"


def build_neo4j_query_pack(selected_rule: str, row: pd.Series) -> dict[str, str]:
    order_id = quote_cypher_value(row.get("order_id"))
    customer_id = quote_cypher_value(row.get("customer_id"))
    merchant_id = quote_cypher_value(row.get("merchant_id"))
    promo_code = quote_cypher_value(row.get("promotion_code"))
    driver_id = quote_cypher_value(row.get("driver_id"))

    queries: dict[str, str] = {
        "Evidence story for selected order": f"""MATCH (e:FraudEvidence)-[:ABOUT_ORDER]->(o)
WHERE (o:Order AND o.order_id = {order_id})
   OR (o:OrderReference AND o.order_id = {order_id})
OPTIONAL MATCH (e)-[:TRIGGERED_RULE]->(r:Rule)
OPTIONAL MATCH (e)-[:SCORED_BY_MODEL]->(m:ModelVersion)
OPTIONAL MATCH (e)-[:ABOUT_CUSTOMER]->(c)
RETURN e, r, m, o, c
ORDER BY e.event_time;""",
        "Customer neighborhood": f"""MATCH (c:Customer {{customer_id: {customer_id}}})-[:PLACED]->(o:Order)
OPTIONAL MATCH (o)-[:PAID_BY]->(pm:PaymentMethod)
OPTIONAL MATCH (o)-[:DROPOFF_AT]->(drop:Address)
OPTIONAL MATCH (o)-[:FROM_MERCHANT]->(m:Merchant)
OPTIONAL MATCH (o)<-[:SERVED]-(d:Driver)
OPTIONAL MATCH (o)-[:USED_PROMO]->(p:PromotionCode)
RETURN c, o, pm, drop, m, d, p
ORDER BY o.order_time DESC
LIMIT 200;""",
    }

    if selected_rule == "PROMO_ENTITY_CONCENTRATION":
        queries["Promo-merchant cluster"] = f"""MATCH (p:PromotionCode {{code: {promo_code}}})<-[:USED_PROMO]-(o:Order)-[:FROM_MERCHANT]->(m:Merchant {{merchant_id: {merchant_id}}})
OPTIONAL MATCH (o)<-[:PLACED]-(c:Customer)
OPTIONAL MATCH (o)-[:PAID_BY]->(pm:PaymentMethod)
OPTIONAL MATCH (o)-[:DROPOFF_AT]->(drop:Address)
OPTIONAL MATCH (o)<-[:SERVED]-(d:Driver)
RETURN p, m, o, c, pm, drop, d
LIMIT 300;"""
    elif selected_rule == "IMPOSSIBLE_TRAVEL":
        queries["Customer timeline around hop"] = f"""MATCH (c:Customer {{customer_id: {customer_id}}})-[:PLACED]->(o:Order)
OPTIONAL MATCH (o)-[:FROM_MERCHANT]->(m:Merchant)
OPTIONAL MATCH (o)-[:PICKUP_AT]->(pickup:Address)
RETURN c, o, m, pickup
ORDER BY o.order_time DESC
LIMIT 50;"""
    elif selected_rule == "FIXED_VALUE_PATTERN":
        queries["Customer-merchant repeated values"] = f"""MATCH (c:Customer {{customer_id: {customer_id}}})-[:PLACED]->(o:Order)-[:FROM_MERCHANT]->(m:Merchant {{merchant_id: {merchant_id}}})
OPTIONAL MATCH (o)-[:USED_PROMO]->(p:PromotionCode)
OPTIONAL MATCH (o)<-[:SERVED]-(d:Driver)
RETURN c, m, o, p, d
ORDER BY o.order_time DESC
LIMIT 200;"""
    elif selected_rule == "MULTI_LINK_DRIVER":
        queries["Driver linked suspicious pairs"] = f"""MATCH (d:Driver {{driver_id: {driver_id}}})-[:SERVED]->(o:Order)
OPTIONAL MATCH (o)<-[:PLACED]-(c:Customer)
OPTIONAL MATCH (o)-[:FROM_MERCHANT]->(m:Merchant)
OPTIONAL MATCH (o)-[:USED_PROMO]->(p:PromotionCode)
RETURN d, o, c, m, p
ORDER BY o.order_time DESC
LIMIT 300;"""
    elif selected_rule == "HIGH_DISCOUNT_OUTLIER":
        queries["Merchant promo context"] = f"""MATCH (o:Order {{order_id: {order_id}}})-[:FROM_MERCHANT]->(m:Merchant)
OPTIONAL MATCH (o)-[:USED_PROMO]->(p:PromotionCode)
OPTIONAL MATCH (o)<-[:PLACED]-(c:Customer)
OPTIONAL MATCH (other:Order)-[:FROM_MERCHANT]->(m)
OPTIONAL MATCH (other)-[:USED_PROMO]->(p)
RETURN o, m, p, c, collect(DISTINCT other)[0..100] AS peer_orders;"""
    elif selected_rule == "FOOD_FULFILLMENT_TIME_OUTLIER":
        queries["Order timeline"] = f"""MATCH (o:Order {{order_id: {order_id}}})
OPTIONAL MATCH (o)-[:HAS_TIMELINE_EVENT]->(event:TimelineEvent)
OPTIONAL MATCH (o)-[:FROM_MERCHANT]->(m:Merchant)
OPTIONAL MATCH (o)<-[:SERVED]-(d:Driver)
RETURN o, event, m, d
ORDER BY event.event_time;"""
    elif selected_rule == "REPEATED_CUSTOMER_DRIVER":
        queries["Customer-driver repetition"] = f"""MATCH (c:Customer {{customer_id: {customer_id}}})-[:PLACED]->(o:Order)<-[:SERVED]-(d:Driver {{driver_id: {driver_id}}})
OPTIONAL MATCH (o)-[:FROM_MERCHANT]->(m:Merchant)
OPTIONAL MATCH (o)-[:DROPOFF_AT]->(drop:Address)
RETURN c, d, o, m, drop
ORDER BY o.order_time DESC
LIMIT 200;"""
        queries["Selected order details"] = f"""MATCH (o:Order {{order_id: {order_id}}})
OPTIONAL MATCH (o)<-[:PLACED]-(c:Customer)
OPTIONAL MATCH (o)<-[:SERVED]-(d:Driver)
OPTIONAL MATCH (o)-[:PICKUP_AT]->(pickup:Address)
OPTIONAL MATCH (o)-[:DROPOFF_AT]->(drop:Address)
OPTIONAL MATCH (o)-[:PAID_BY]->(pm:PaymentMethod)
OPTIONAL MATCH (o)-[:USED_PROMO]->(p:PromotionCode)
RETURN o, c, d, pickup, drop, pm, p;"""
        queries["Customer timeline and linked drivers"] = f"""MATCH (c:Customer {{customer_id: {customer_id}}})-[:PLACED]->(o:Order)
OPTIONAL MATCH (o)<-[:SERVED]-(d:Driver)
OPTIONAL MATCH (o)-[:PICKUP_AT]->(pickup:Address)
OPTIONAL MATCH (o)-[:DROPOFF_AT]->(drop:Address)
RETURN c, o, d, pickup, drop
ORDER BY o.order_time DESC
LIMIT 200;"""
        queries["Driver timeline and linked customers"] = f"""MATCH (d:Driver {{driver_id: {driver_id}}})-[:SERVED]->(o:Order)
OPTIONAL MATCH (o)<-[:PLACED]-(c:Customer)
OPTIONAL MATCH (o)-[:PICKUP_AT]->(pickup:Address)
OPTIONAL MATCH (o)-[:DROPOFF_AT]->(drop:Address)
RETURN d, o, c, pickup, drop
ORDER BY o.order_time DESC
LIMIT 200;"""
        queries["Pair route and time reuse"] = f"""MATCH (c:Customer {{customer_id: {customer_id}}})-[:PLACED]->(o:Order)<-[:SERVED]-(d:Driver {{driver_id: {driver_id}}})
OPTIONAL MATCH (o)-[:PICKUP_AT]->(pickup:Address)
OPTIONAL MATCH (o)-[:DROPOFF_AT]->(drop:Address)
RETURN o.order_id AS order_id, o.order_time AS order_time, pickup.address AS pickup_address, drop.address AS dropoff_address
ORDER BY o.order_time DESC
LIMIT 200;"""

    return queries


def legacy_main() -> None:
    st.set_page_config(page_title="KB-C Collusion Review", layout="wide")
    st.title("KB-C Driver-Customer Collusion Review")

    report_dir = st.sidebar.text_input("Report directory", str(REPORT_DIR))
    reports = read_reports(report_dir)
    daily = add_rule_display(reports["daily"])
    comparison = add_rule_display(reports["comparison"])
    recommendations = add_rule_display(reports["recommendations"])
    quality = reports["quality"]
    flags = add_rule_display(reports["flags"])
    kbc_pairs = reports["kbc_pairs"]
    kbc_reasons = reports["kbc_reasons"]
    kbc_known = reports["kbc_known"]
    kbc_daily = build_kbc_daily_summary(daily)

    if kbc_daily.empty or kbc_pairs.empty:
        st.warning("No KB-C report found. Run `python -m scripts.build_task3_daily_outputs` first.")
        return
    st.sidebar.markdown("### Filters")
    high_conf_only = st.sidebar.checkbox("High confidence only", value=True)
    min_trips = int(kbc_pairs["n_trips"].min()) if "n_trips" in kbc_pairs.columns else 0
    max_trips = int(kbc_pairs["n_trips"].max()) if "n_trips" in kbc_pairs.columns else 0
    trip_cutoff = st.sidebar.slider("Min n_trips", min_trips, max_trips, min(12, max_trips) if max_trips else 0)
    max_gap_default = min(10.0, float(kbc_pairs["min_gap_min"].max())) if "min_gap_min" in kbc_pairs.columns else 10.0
    gap_cutoff = st.sidebar.slider("Max min_gap_min", 0.0, max(10.0, max_gap_default), 5.0, 0.5)
    ghost_cutoff = st.sidebar.slider("Min ghost_rate", 0.0, 1.0, 0.0, 0.05)

    filtered_kbc_pairs = kbc_pairs.copy()
    if "latest_order_date" in filtered_kbc_pairs.columns:
        filtered_kbc_pairs["latest_order_date"] = pd.to_datetime(filtered_kbc_pairs["latest_order_date"], errors="coerce").dt.date
    filtered_kbc_pairs = filtered_kbc_pairs[
        (filtered_kbc_pairs["n_trips"] >= trip_cutoff)
        & (filtered_kbc_pairs["min_gap_min"] <= gap_cutoff)
        & (filtered_kbc_pairs["ghost_rate"] >= ghost_cutoff)
    ]
    if high_conf_only and "high_confidence" in filtered_kbc_pairs.columns:
        filtered_kbc_pairs = filtered_kbc_pairs[filtered_kbc_pairs["high_confidence"].fillna(False)]

    filtered_kbc_reasons = kbc_reasons.merge(
        filtered_kbc_pairs[["driver_id", "customer_id"]],
        on=["driver_id", "customer_id"],
        how="inner",
    ) if not kbc_reasons.empty else pd.DataFrame()

    filtered_flags = flags.merge(
        filtered_kbc_pairs[["driver_id", "customer_id"]],
        on=["driver_id", "customer_id"],
        how="inner",
    ) if not flags.empty else pd.DataFrame()

    window_metrics = build_window_metrics(filtered_flags)
    customer_summary = build_entity_summary(filtered_flags, "customer_id")
    driver_summary = build_entity_summary(filtered_flags, "driver_id")
    order_reason_summary = build_order_reason_summary(filtered_flags)

    st.subheader("1. Overall Picture")
    st.markdown(
        "Phần này cho biết quy mô bất thường hiện tại và ý nghĩa của các chỉ số chính, trước khi đi xuống từng cặp cụ thể."
    )

    if not window_metrics.empty:
        st.caption("Flag volume by monitoring window")
        window_cols = st.columns(len(window_metrics))
        for idx, row in window_metrics.reset_index(drop=True).iterrows():
            window_cols[idx].metric(
                f"{row['window_label']} flagged orders",
                f"{int(row['flagged_orders']):,}",
                help=f"Từ {row['start_date']} đến {row['end_date']}",
            )
        window_detail_cols = st.columns(len(window_metrics))
        for idx, row in window_metrics.reset_index(drop=True).iterrows():
            with window_detail_cols[idx]:
                st.caption(
                    f"pairs `{int(row['flagged_pairs']):,}` | customers `{int(row['flagged_customers']):,}` | "
                    f"drivers `{int(row['flagged_drivers']):,}` | high-conf orders `{int(row['high_conf_orders']):,}`"
                )

    overview_cols = st.columns(5)
    overview_cols[0].metric("Flagged pairs", f"{len(filtered_kbc_pairs):,}")
    overview_cols[1].metric("High-confidence pairs", f"{int(filtered_kbc_pairs['high_confidence'].fillna(False).sum()):,}" if "high_confidence" in filtered_kbc_pairs.columns else "0")
    overview_cols[2].metric("Flagged orders", f"{int(filtered_flags['order_id'].nunique()):,}" if not filtered_flags.empty else "0")
    overview_cols[3].metric("Min gap", f"{float(filtered_kbc_pairs['min_gap_min'].min()):.2f} min" if not filtered_kbc_pairs.empty else "n/a")
    overview_cols[4].metric("Max ghost rate", f"{float(filtered_kbc_pairs['ghost_rate'].max()):.0%}" if not filtered_kbc_pairs.empty else "n/a")

    st.caption("What this dashboard is looking for")
    st.dataframe(build_rule_review_context("REPEATED_CUSTOMER_DRIVER"), use_container_width=True, hide_index=True)
    st.caption("Metric guide")
    st.dataframe(build_kbc_metric_guide(), use_container_width=True, hide_index=True)

    st.subheader("2. Summary Trend")
    st.markdown(
        "Phần này trả lời câu hỏi: số order bị flag thay đổi theo ngày thế nào, và lý do nào đang xuất hiện nhiều nhất."
    )
    top_left, top_right = st.columns([2, 1])
    with top_left:
        trend_fig = px.bar(
            kbc_daily,
            x="order_date",
            y="flagged_orders",
            text="flagged_orders",
            title="Daily flagged orders",
        )
        trend_fig.update_traces(textposition="outside")
        st.plotly_chart(trend_fig, use_container_width=True)
    with top_right:
        reason_pair_summary = build_kbc_reason_pair_summary(filtered_kbc_reasons)
        if not reason_pair_summary.empty:
            reason_fig = px.bar(
                reason_pair_summary,
                x="flagged_pairs",
                y="reason_code",
                orientation="h",
                title="Pairs by reason",
            )
            st.plotly_chart(reason_fig, use_container_width=True)

    mid_left, mid_right = st.columns(2)
    with mid_left:
        if not customer_summary.empty:
            customer_fig = px.bar(
                customer_summary.head(15),
                x="customer_id",
                y="flagged_orders",
                title="Customers with most flagged orders",
                hover_data=["high_conf_orders", "max_n_trips", "max_ghost_rate", "min_gap_min"],
            )
            st.plotly_chart(customer_fig, use_container_width=True)
    with mid_right:
        if not driver_summary.empty:
            driver_fig = px.bar(
                driver_summary.head(15),
                x="driver_id",
                y="flagged_orders",
                title="Drivers with most flagged orders",
                hover_data=["high_conf_orders", "max_n_trips", "max_ghost_rate", "min_gap_min"],
            )
            st.plotly_chart(driver_fig, use_container_width=True)

    st.subheader("3. Risk Map")
    st.markdown(
        "Biểu đồ này giúp nhìn nhanh cặp nào đáng nghi hơn: càng sang trái thì khoảng cách chuyến càng ngắn, càng lên cao thì tỷ lệ ghost trip càng lớn."
    )
    chart_col, note_col = st.columns([3, 2])
    with chart_col:
        scatter_data = filtered_kbc_pairs.sort_values(["high_confidence", "n_trips", "rule_score"], ascending=[False, False, False]).head(100)
        scatter_fig = px.scatter(
            scatter_data,
            x="min_gap_min",
            y="ghost_rate",
            size="n_trips",
            color="high_confidence",
            hover_data=["driver_id", "customer_id", "avg_gmv", "rule_score"],
            title="Pair severity map: lower gap and higher ghost rate are riskier",
        )
        st.plotly_chart(scatter_fig, use_container_width=True)
    with note_col:
        st.markdown("**How to read this view**")
        st.markdown(
            "\n".join(
                [
                    "- Pairs far left: trips are repeated very quickly.",
                    "- Pairs high on chart: larger share of `avg_kmh = 0` rides.",
                    "- Larger bubbles: more total trips for the same driver-customer pair.",
                    "- Red points: meet the current `high_confidence` condition.",
                ]
            )
        )

    st.subheader("4. Top Suspicious Pairs")
    st.markdown(
        "Bảng dưới đây là danh sách ưu tiên review. Mỗi dòng tương ứng với một cặp tài xế-khách hàng đã được tổng hợp ở cấp pair."
    )
    preferred_pair_columns = [
        "driver_id",
        "customer_id",
        "n_trips",
        "n_ghost",
        "ghost_rate",
        "min_gap_min",
        "high_confidence",
        "avg_gmv",
        "rule_score",
        "pair_share_driver",
        "pair_share_customer",
        "dominant_route_share",
        "top_service_name",
        "latest_order_date",
    ]
    visible_pair_columns = [column for column in preferred_pair_columns if column in filtered_kbc_pairs.columns]
    pair_table = filtered_kbc_pairs.sort_values(
        ["high_confidence", "n_trips", "rule_score"],
        ascending=[False, False, False],
    )[visible_pair_columns].head(100)
    st.dataframe(pair_table, use_container_width=True, hide_index=True)

    entity_left, entity_right = st.columns(2)
    with entity_left:
        if not customer_summary.empty:
            st.caption("Top customers")
            st.dataframe(customer_summary.head(20), use_container_width=True, hide_index=True)
    with entity_right:
        if not driver_summary.empty:
            st.caption("Top drivers")
            st.dataframe(driver_summary.head(20), use_container_width=True, hide_index=True)

    if filtered_kbc_pairs.empty:
        st.info("No pair matches the current filters.")
        return

    st.subheader("5. Pair Detail")
    st.markdown(
        "Sau khi chọn một cặp, phần này giải thích vì sao cặp đó bị flag và hiển thị các order liên quan để drill-down."
    )
    pair_options = (
        filtered_kbc_pairs.sort_values(["high_confidence", "n_trips", "rule_score"], ascending=[False, False, False])
        .assign(
            pair_label=lambda df: df.apply(
                lambda row: f"{row['driver_id']} | {row['customer_id']} | trips={int(row['n_trips'])} | gap={float(row['min_gap_min']):.2f}m | ghost={float(row['ghost_rate']):.0%}",
                axis=1,
            )
        )
    )
    selected_pair_label = st.selectbox("Selected pair", pair_options["pair_label"].head(100).tolist(), index=0)
    selected_pair = pair_options.loc[pair_options["pair_label"] == selected_pair_label].iloc[0]

    detail_left, detail_right = st.columns([2, 1])
    with detail_left:
        st.subheader("Selected pair details")
        st.dataframe(
            pd.DataFrame(
                [
                    {"metric": "driver_id", "value": selected_pair["driver_id"]},
                    {"metric": "customer_id", "value": selected_pair["customer_id"]},
                    {"metric": "n_trips", "value": int(selected_pair["n_trips"])},
                    {"metric": "n_ghost", "value": int(selected_pair["n_ghost"])},
                    {"metric": "ghost_rate", "value": f"{float(selected_pair['ghost_rate']):.2%}"},
                    {"metric": "min_gap_min", "value": f"{float(selected_pair['min_gap_min']):.2f}"},
                    {"metric": "avg_gmv", "value": f"{float(selected_pair['avg_gmv']):,.0f}"},
                    {"metric": "rule_score", "value": f"{float(selected_pair['rule_score']):.2f}"},
                    {"metric": "high_confidence", "value": bool(selected_pair["high_confidence"])},
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
    with detail_right:
        pair_reason_rows = filtered_kbc_reasons[
            (filtered_kbc_reasons["driver_id"] == selected_pair["driver_id"])
            & (filtered_kbc_reasons["customer_id"] == selected_pair["customer_id"])
        ]
        st.subheader("Why this pair was flagged")
        st.dataframe(
            pair_reason_rows[["reason_code", "flag_reason", "supporting_signal"]].drop_duplicates(),
            use_container_width=True,
            hide_index=True,
        )

    if not filtered_flags.empty:
        pair_orders = filtered_flags[
            (filtered_flags["driver_id"] == selected_pair["driver_id"])
            & (filtered_flags["customer_id"] == selected_pair["customer_id"])
        ].copy()
        pair_orders = pair_orders.sort_values("order_time_local_tz")
        sample_columns = [
            "order_id",
            "order_time_local_tz",
            "complete_time_local_tz",
            "service_name",
            "avg_kmh",
            "gmv",
            "reason_code",
            "pickup_address",
            "last_dropoff_address",
        ]
        st.subheader("Orders for selected pair")
        st.dataframe(pair_orders[[col for col in sample_columns if col in pair_orders.columns]].head(200), use_container_width=True, hide_index=True)

        selected_case = pair_orders.iloc[0]
        st.caption("Top flagged orders by reason")
        if not order_reason_summary.empty:
            st.dataframe(order_reason_summary, use_container_width=True, hide_index=True)
        with st.expander("Neo4j drill-down queries", expanded=False):
            st.markdown(f"Browser: `{settings.neo4j_ride_browser_url}`")
            st.markdown(f"Bolt: `{settings.neo4j_ride_uri}`")
            for title, query in build_neo4j_query_pack("REPEATED_CUSTOMER_DRIVER", selected_case).items():
                st.caption(title)
                st.code(query, language="cypher")

    if not kbc_known.empty:
        st.subheader("6. Known-Case Validation")
        st.markdown(
            "Phần này dùng để sanity check rule với case fraud đã biết hoặc case seed mà nhóm đang theo dõi."
        )
        st.dataframe(kbc_known, use_container_width=True, hide_index=True)

    with st.expander("Operational notes", expanded=False):
        if not quality.empty:
            st.caption("Data quality")
            st.dataframe(quality, use_container_width=True, hide_index=True)
        if not recommendations.empty:
            st.caption("Recommendation")
            st.dataframe(recommendations[["priority_score", "recommendation", "flagged_orders", "total_gmv", "total_discount"]], use_container_width=True, hide_index=True)
        if not comparison.empty:
            st.caption("Rule summary")
            st.dataframe(comparison, use_container_width=True, hide_index=True)


def main() -> None:
    from src.dashboard.kbc_daily_dashboard import render_dashboard

    render_dashboard()


if __name__ == "__main__":
    main()
