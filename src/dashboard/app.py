"""Task 3 dashboard for daily rule/model and graph-case review."""

from __future__ import annotations

from pathlib import Path

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
    "REPEATED_CUSTOMER_DRIVER": "Repeated Customer-Driver Pair",
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
    }.items():
        path = root / filename
        if not path.exists():
            reports[name] = pd.DataFrame()
        elif path.suffix == ".parquet":
            reports[name] = pd.read_parquet(path)
        else:
            reports[name] = pd.read_csv(path)
    return reports


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
            "fraud_behavior": "A customer repeatedly rides with the same driver within one day, suggesting collusion or self-dealing.",
            "analyst_readability": "Analyst should read pair order count and pair ratio immediately.",
            "false_positive_risk": "Small local zones or sticky merchant-driver routing can cause legitimate repetition.",
            "neo4j_drilldown": "Start from Customer and Driver, then inspect repeated Orders, Merchant, and Address nodes.",
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
        summary = rule_flags.groupby(group_cols, dropna=False).agg(
            flagged_orders=("order_id", "nunique"),
            avg_rule_score=("rule_score", "mean"),
            max_pair_orders=("pair_orders", "max"),
            max_pair_ratio=("pair_ratio", "max"),
        ).reset_index()
        return summary.sort_values(["flagged_orders", "max_pair_orders", "avg_rule_score"], ascending=False)

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
            "Check whether the same customer-driver pair repeats unusually often within one day.",
            "Check whether those orders also converge on the same merchant or address.",
            "If the pattern is isolated to a tiny local zone, keep a legitimate-routing explanation open.",
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

    return queries


def main() -> None:
    st.set_page_config(page_title="Task 3 Graph Anti-Fraud", layout="wide")
    st.title("Task 3 Graph Anti-Fraud")

    report_dir = st.sidebar.text_input("Report directory", str(REPORT_DIR))
    reports = read_reports(report_dir)
    daily = add_rule_display(reports["daily"])
    comparison = add_rule_display(reports["comparison"])
    recommendations = add_rule_display(reports["recommendations"])
    quality = reports["quality"]
    flags = add_rule_display(reports["flags"])
    anomalies = reports["anomalies"]

    if daily.empty:
        st.warning("No daily report found. Run `python -m scripts.build_task3_daily_outputs` first.")
        return

    domains = sorted(daily["domain"].dropna().unique())
    selected_domains = st.sidebar.multiselect("Domain", domains, default=domains)
    filtered_daily = daily[daily["domain"].isin(selected_domains)] if selected_domains else daily

    metric_cols = st.columns(4)
    metric_cols[0].metric("Flagged orders", f"{int(filtered_daily['flagged_orders'].sum()):,}")
    metric_cols[1].metric("Flagged customers", f"{int(filtered_daily['flagged_customers'].sum()):,}")
    metric_cols[2].metric("Rules", f"{filtered_daily['rule_name'].nunique():,}")
    metric_cols[3].metric("Model overlap", f"{int(filtered_daily['model_overlap_orders'].sum()):,}")

    st.subheader("Daily flagged orders by rule")
    fig = px.bar(
        filtered_daily,
        x="order_date",
        y="flagged_orders",
        color="rule_display_name",
        facet_col="domain",
        barmode="stack",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Rule vs model anomaly comparison")
    if not comparison.empty:
        st.dataframe(
            comparison.sort_values(["model_overlap_rate", "flagged_orders"], ascending=False),
            use_container_width=True,
            hide_index=True,
        )

    st.subheader("Priority recommendations")
    if not recommendations.empty:
        st.dataframe(
            recommendations[
                [
                    "domain",
                    "rule_display_name",
                    "rule_name",
                    "priority_score",
                    "recommendation",
                    "flagged_orders",
                    "avg_anomaly_score",
                    "model_overlap_rate",
                    "total_discount",
                    "total_gmv",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

    st.subheader("Data quality checks")
    if not quality.empty:
        st.dataframe(quality, use_container_width=True, hide_index=True)

    st.subheader("Rule-level review")
    if not flags.empty:
        filtered_flags = flags[flags["domain"].isin(selected_domains)] if selected_domains else flags
        available_rules = sorted(filtered_flags["rule_name"].dropna().unique())
        rule_labels = rule_option_labels(available_rules)
        selected_rule_label = st.selectbox("Rule review", [rule_labels[rule_name] for rule_name in available_rules], index=0)
        selected_rule = next(rule_name for rule_name, label in rule_labels.items() if label == selected_rule_label)
        rule_flags = filtered_flags[filtered_flags["rule_name"] == selected_rule].copy()

        st.caption("Anti-Fraud validation guide")
        st.dataframe(build_rule_review_context(selected_rule), use_container_width=True, hide_index=True)

        reason_breakdown = build_reason_breakdown(rule_flags)
        if not reason_breakdown.empty:
            left_col, right_col = st.columns([1, 2])
            with left_col:
                st.caption("Reason breakdown")
                st.dataframe(reason_breakdown, use_container_width=True, hide_index=True)
            with right_col:
                reason_fig = px.bar(
                    reason_breakdown,
                    x="reason_code",
                    y="flagged_orders",
                    color="reason_code",
                )
                reason_fig.update_layout(showlegend=False)
                st.plotly_chart(reason_fig, use_container_width=True)

        cluster_summary = build_rule_cluster_summary(rule_flags, selected_rule)
        if not cluster_summary.empty:
            st.caption("Top clusters for selected rule")
            st.dataframe(cluster_summary.head(100), use_container_width=True, hide_index=True)

        preferred_columns = [
            "order_id",
            "customer_id",
            "rule_display_name",
            "rule_name",
            "reason_code",
            "rule_score",
            "risk_tier",
            "supporting_signal",
            "flag_reason",
            "service_name",
            "merchant_id",
            "promotion_code",
            "driver_id",
            "pickup_province_name",
            "previous_pickup_province_name",
            "province_pair",
            "time_gap_hours",
            "impossible_travel_count",
            "order_amount_value",
            "fixed_value_order_count",
            "fixed_value_cv",
            "linked_pair_count",
            "linked_discount_total",
            "shared_signal_count",
            "merchant_order_share",
            "merchant_customer_share",
            "customer_repeat_ratio",
            "payment_share",
            "dropoff_share",
            "driver_share",
            "discount_rate",
            "lead_time_second",
            "pair_orders",
            "pair_ratio",
        ]
        visible_columns = [column for column in preferred_columns if column in rule_flags.columns]
        fallback_columns = [column for column in rule_flags.columns if column not in visible_columns]
        if "supporting_signal" in rule_flags.columns and rule_flags["supporting_signal"].notna().any():
            st.caption("Supporting signals captured after rule consolidation")
            support_summary = (
                rule_flags[rule_flags["supporting_signal"].notna()]
                .groupby(["supporting_signal"], dropna=False)
                .agg(
                    flagged_orders=("order_id", "nunique"),
                    flagged_customers=("customer_id", "nunique"),
                    avg_rule_score=("rule_score", "mean"),
                )
                .reset_index()
                .sort_values(["flagged_orders", "avg_rule_score"], ascending=False)
            )
            st.dataframe(support_summary, use_container_width=True, hide_index=True)

        st.caption("Sample flagged rows")
        st.dataframe(
            rule_flags[visible_columns + fallback_columns].head(200),
            use_container_width=True,
            hide_index=True,
        )

        review_candidates = rule_flags[visible_columns + fallback_columns].copy().reset_index(drop=True)
        review_candidates["review_label"] = review_candidates.apply(
            lambda row: " | ".join(
                [
                    str(row.get("order_id", "")),
                    str(row.get("customer_id", "")),
                    str(row.get("reason_code", "")),
                    str(row.get("merchant_id", "")),
                    str(row.get("promotion_code", "")),
                ]
            ).strip(" |"),
            axis=1,
        )
        selected_label = st.selectbox(
            "Neo4j drill-down case",
            review_candidates["review_label"].head(100).tolist(),
            index=0,
        )
        selected_case = review_candidates.loc[review_candidates["review_label"] == selected_label].iloc[0]
        st.caption("Neo4j Browser workflow")
        with st.expander("How to use with Docker + Neo4j Browser", expanded=False):
            st.markdown(
                """
1. Start Neo4j with Docker and make sure Neo4j Browser is reachable.
2. Open the Neo4j Browser for the domain you want to inspect and sign in.
3. Check the active dashboard domain before copying a query.
4. In the dashboard, choose a row under `Neo4j drill-down case`.
5. Copy one query from `Neo4j drill-down queries` and paste it into Neo4j Browser.
6. Read the returned graph with the checklist below before concluding fraud.
                """
            )
            st.code("docker ps", language="bash")
            st.markdown(f"Active domain: `{settings.neo4j_domain}`")
            st.markdown(f"Active Bolt URI: `{settings.neo4j_uri}`")
            st.markdown("Browser URLs:")
            st.code(
                "\n".join(
                    [
                        f"food: {settings.neo4j_food_browser_url}",
                        f"ride: {settings.neo4j_ride_browser_url}",
                        f"active_{settings.neo4j_domain}: {settings.neo4j_browser_url}",
                    ]
                ),
                language="text",
            )

        st.caption("What to verify in Neo4j Browser")
        st.dataframe(build_browser_checklist(selected_rule), use_container_width=True, hide_index=True)

        st.caption("Neo4j drill-down queries")
        for title, query in build_neo4j_query_pack(selected_rule, selected_case).items():
            with st.expander(title, expanded=False):
                st.code(query, language="cypher")

    st.subheader("Anomaly score sample")
    if not anomalies.empty:
        filtered_anomalies = anomalies[anomalies["domain"].isin(selected_domains)] if selected_domains else anomalies
        st.dataframe(
            filtered_anomalies.sort_values("anomaly_score", ascending=False).head(100),
            use_container_width=True,
            hide_index=True,
        )


if __name__ == "__main__":
    main()
