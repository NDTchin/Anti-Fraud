"""KB-C daily fraud dashboard."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


REPORT_DIR = Path("reports/task3")
ALL_OPTION = "__all__"

GRANULARITY_CONFIG = {
    "Ngày": "order_day",
    "Tuần": "order_week",
    "Tháng": "order_month",
}

METRIC_OPTIONS = {
    "Đơn bị flag": "flagged_orders",
    "Tài xế bị flag": "flagged_drivers",
    "Khách hàng bị flag": "flagged_customers",
    "Cặp tài xế - khách hàng": "flagged_pairs",
}

FLAG_REASON_VI = {
    "Driver-customer pair is an extreme weighted edge in the current analysis window.": "Cặp tài xế - khách hàng này lặp lại với tần suất rất cao trong cửa sổ phân tích hiện tại.",
    "The suspicious pair belongs to a connected component with shared supporting entities.": "Cặp này nằm trong một nhóm liên kết đáng nghi và chia sẻ đầu mối với nhiều cặp khác.",
    "Driver-customer pair creates consecutive trips too quickly to look operationally normal.": "Cặp này tạo các chuyến liên tiếp quá nhanh, không giống vận hành bình thường.",
    "The pair absorbs an unusually large share of both the driver and customer activity.": "Cặp này chiếm tỷ trọng bất thường trong tổng hoạt động của cả tài xế và khách hàng.",
}

SUPPORTING_SIGNAL_VI = {
    "weighted_edge_outlier": "Tần suất lặp lại của cặp cao bất thường",
    "wcc_component_support": "Được củng cố bởi nhóm liên kết WCC",
    "temporal_turnaround": "Khoảng cách giữa các chuyến quá ngắn",
    "bipartite_pair_concentration": "Mức độ phụ thuộc hai chiều giữa tài xế và khách hàng quá cao",
}

DETAIL_COLUMN_LABELS = {
    "order_id": "Mã đơn hàng",
    "order_date": "Ngày đơn hàng",
    "driver_id": "Mã tài xế",
    "customer_id": "Mã khách hàng",
    "service_name": "Dịch vụ",
    "business_rule_label": "Rule fraud nghiệp vụ",
    "reason_code": "Mã lý do flag",
    "priority_score": "Điểm ưu tiên điều tra",
    "ghost_rate": "Tỷ lệ chuyến ghost",
    "n_trips": "Số chuyến trong cặp",
    "component_id": "Mã nhóm rủi ro",
    "component_size": "Kích thước nhóm",
    "risk_tier": "Mức độ rủi ro",
    "network_support_score": "Điểm hỗ trợ mạng liên kết",
    "business_rule_story": "Câu chuyện của rule",
    "flag_reason_vi": "Diễn giải lý do bị flag",
    "supporting_signal_vi": "Tín hiệu hỗ trợ",
}

PAIR_COLUMN_LABELS = {
    "driver_id": "Mã tài xế",
    "customer_id": "Mã khách hàng",
    "top_service_name": "Dịch vụ chính",
    "primary_business_rule_label": "Rule chính",
    "primary_business_rule_story": "Câu chuyện của rule",
    "priority_score": "Điểm ưu tiên",
    "ghost_rate": "Tỷ lệ ghost trip",
    "n_trips": "Số chuyến",
    "component_id": "Mã nhóm rủi ro",
}


@st.cache_data(show_spinner=False)
def load_reports(report_dir: str) -> dict[str, pd.DataFrame]:
    root = Path(report_dir)
    reports: dict[str, pd.DataFrame] = {}
    files = {
        "flags": "flagged_orders.parquet",
        "pairs": "kbc_pair_summary.csv",
        "reasons": "kbc_pair_reasons.csv",
    }
    for key, filename in files.items():
        path = root / filename
        if not path.exists():
            reports[key] = pd.DataFrame()
        elif path.suffix == ".parquet":
            reports[key] = pd.read_parquet(path)
        else:
            reports[key] = pd.read_csv(path)
    return reports


def _normalize_flags(flags: pd.DataFrame) -> pd.DataFrame:
    if flags.empty:
        return flags
    frame = flags.copy()
    frame["order_date"] = pd.to_datetime(frame.get("order_date"), errors="coerce")
    frame = frame.dropna(subset=["order_date"]).copy()
    frame["order_day"] = frame["order_date"].dt.normalize()
    frame["order_week"] = frame["order_date"].dt.to_period("W-SUN").dt.start_time
    frame["order_month"] = frame["order_date"].dt.to_period("M").dt.start_time
    if "flag_reason" in frame.columns:
        frame["flag_reason_vi"] = frame["flag_reason"].map(FLAG_REASON_VI).fillna(frame["flag_reason"])
    if "supporting_signal" in frame.columns:
        frame["supporting_signal_vi"] = frame["supporting_signal"].map(SUPPORTING_SIGNAL_VI).fillna(frame["supporting_signal"])
    return frame


def _normalize_pairs(pairs: pd.DataFrame) -> pd.DataFrame:
    if pairs.empty:
        return pairs
    frame = pairs.copy()
    if "latest_order_date" in frame.columns:
        frame["latest_order_date"] = pd.to_datetime(frame["latest_order_date"], errors="coerce")
    return frame


def _normalize_reasons(reasons: pd.DataFrame) -> pd.DataFrame:
    if reasons.empty:
        return reasons
    frame = reasons.copy()
    if "latest_order_date" in frame.columns:
        frame["latest_order_date"] = pd.to_datetime(frame["latest_order_date"], errors="coerce")
    if "flag_reason" in frame.columns:
        frame["flag_reason_vi"] = frame["flag_reason"].map(FLAG_REASON_VI).fillna(frame["flag_reason"])
    return frame


def _render_filters(flags: pd.DataFrame) -> dict[str, object]:
    min_date = flags["order_date"].min().date()
    max_date = flags["order_date"].max().date()
    rule_options = [ALL_OPTION]
    if "business_rule_label" in flags.columns:
        rule_options += sorted(flags["business_rule_label"].dropna().astype(str).unique().tolist())

    col1, col2, col3, col4 = st.columns([1.2, 1, 1, 1.2])
    with col1:
        date_range = st.date_input(
            "Khoảng ngày",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )
    with col2:
        service_options = [ALL_OPTION] + sorted(flags["service_name"].dropna().astype(str).unique().tolist())
        selected_service = st.selectbox(
            "Dịch vụ",
            options=service_options,
            index=0,
            format_func=lambda value: "Tất cả" if value == ALL_OPTION else value,
        )
    with col3:
        risk_options = [ALL_OPTION] + sorted(flags["risk_tier"].dropna().astype(str).unique().tolist())
        selected_risk = st.selectbox(
            "Mức rủi ro",
            options=risk_options,
            index=0,
            format_func=lambda value: "Tất cả" if value == ALL_OPTION else value,
        )
    with col4:
        selected_rule = st.selectbox(
            "Rule fraud",
            options=rule_options,
            index=0,
            format_func=lambda value: "Tất cả" if value == ALL_OPTION else value,
        )

    if isinstance(date_range, tuple):
        if len(date_range) == 2 and not isinstance(date_range[0], tuple):
            start_date, end_date = date_range
        elif len(date_range) == 1:
            single_value = date_range[0]
            if isinstance(single_value, tuple) and len(single_value) == 2:
                start_date, end_date = single_value
            else:
                start_date = end_date = single_value
        else:
            start_date = end_date = date_range[0]
    else:
        start_date = end_date = date_range

    return {
        "start_date": start_date,
        "end_date": end_date,
        "service": selected_service,
        "risk_tier": selected_risk,
        "rule": selected_rule,
    }


def _apply_filters(
    flags: pd.DataFrame,
    pairs: pd.DataFrame,
    reasons: pd.DataFrame,
    filters: dict[str, object],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    start_date_raw = filters["start_date"]
    end_date_raw = filters["end_date"]
    if isinstance(start_date_raw, tuple):
        start_date_raw = start_date_raw[0]
    if isinstance(end_date_raw, tuple):
        end_date_raw = end_date_raw[-1]
    start_date = pd.Timestamp(start_date_raw).normalize()
    end_date = pd.Timestamp(end_date_raw).normalize()
    service = str(filters["service"])
    risk_tier = str(filters["risk_tier"])
    selected_rule = str(filters["rule"])

    filtered_flags = flags[flags["order_date"].between(start_date, end_date, inclusive="both")].copy()
    if service != ALL_OPTION and "service_name" in filtered_flags.columns:
        filtered_flags = filtered_flags[filtered_flags["service_name"].astype(str) == service].copy()
    if risk_tier != ALL_OPTION and "risk_tier" in filtered_flags.columns:
        filtered_flags = filtered_flags[filtered_flags["risk_tier"].astype(str) == risk_tier].copy()
    if selected_rule != ALL_OPTION and "business_rule_label" in filtered_flags.columns:
        filtered_flags = filtered_flags[filtered_flags["business_rule_label"].astype(str) == selected_rule].copy()

    filtered_pairs = pairs.copy()
    if not filtered_pairs.empty and "latest_order_date" in filtered_pairs.columns:
        filtered_pairs = filtered_pairs[
            filtered_pairs["latest_order_date"].between(start_date, end_date, inclusive="both")
        ].copy()
    if service != ALL_OPTION and "top_service_name" in filtered_pairs.columns:
        filtered_pairs = filtered_pairs[filtered_pairs["top_service_name"].astype(str) == service].copy()
    if selected_rule != ALL_OPTION and "primary_business_rule_label" in filtered_pairs.columns:
        filtered_pairs = filtered_pairs[
            filtered_pairs["primary_business_rule_label"].astype(str) == selected_rule
        ].copy()

    filtered_reasons = reasons.copy()
    if not filtered_reasons.empty and "latest_order_date" in filtered_reasons.columns:
        filtered_reasons = filtered_reasons[
            filtered_reasons["latest_order_date"].between(start_date, end_date, inclusive="both")
        ].copy()
    if service != ALL_OPTION and "top_service_name" in filtered_reasons.columns:
        filtered_reasons = filtered_reasons[filtered_reasons["top_service_name"].astype(str) == service].copy()
    if selected_rule != ALL_OPTION and "business_rule_label" in filtered_reasons.columns:
        filtered_reasons = filtered_reasons[
            filtered_reasons["business_rule_label"].astype(str) == selected_rule
        ].copy()

    return filtered_flags, filtered_pairs, filtered_reasons


def build_period_summary(flags: pd.DataFrame, period_col: str) -> pd.DataFrame:
    if flags.empty:
        return pd.DataFrame()
    summary = (
        flags.groupby(period_col, dropna=False)
        .agg(
            total_orders_in_scope=("order_id", "nunique"),
            flagged_orders=("order_id", "nunique"),
            flagged_drivers=("driver_id", "nunique"),
            flagged_customers=("customer_id", "nunique"),
        )
        .reset_index()
    )
    pair_counts = (
        flags.groupby(period_col)[["driver_id", "customer_id"]]
        .apply(lambda g: g.drop_duplicates().shape[0])
        .rename("flagged_pairs")
        .reset_index()
    )
    return summary.merge(pair_counts, on=period_col, how="left").rename(
        columns={period_col: "period_start"}
    ).sort_values("period_start")


def build_overview_metrics(flags: pd.DataFrame) -> dict[str, int]:
    if flags.empty:
        return {
            "total_orders_in_scope": 0,
            "flagged_orders": 0,
            "flagged_drivers": 0,
            "flagged_customers": 0,
            "largest_component_size": 0,
        }
    largest_component = int(flags["component_size"].fillna(0).max()) if "component_size" in flags.columns else 0
    return {
        "total_orders_in_scope": int(flags["order_id"].nunique()),
        "flagged_orders": int(flags["order_id"].nunique()),
        "flagged_drivers": int(flags["driver_id"].nunique()) if "driver_id" in flags.columns else 0,
        "flagged_customers": int(flags["customer_id"].nunique()) if "customer_id" in flags.columns else 0,
        "largest_component_size": largest_component,
    }


def build_rule_overview(flags: pd.DataFrame) -> pd.DataFrame:
    if flags.empty or "business_rule_label" not in flags.columns:
        return pd.DataFrame()
    return (
        flags.groupby("business_rule_label", dropna=False)
        .agg(
            flagged_orders=("order_id", "nunique"),
            flagged_customers=("customer_id", "nunique"),
            avg_priority_score=("priority_score", "mean"),
            business_rule_story=("business_rule_story", lambda s: s.dropna().iloc[0] if not s.dropna().empty else ""),
        )
        .reset_index()
        .sort_values(["flagged_orders", "avg_priority_score"], ascending=[False, False])
    )


def build_reason_overview(reasons: pd.DataFrame) -> pd.DataFrame:
    if reasons.empty or "reason_code" not in reasons.columns:
        return pd.DataFrame()
    return (
        reasons.groupby("reason_code", dropna=False)
        .agg(
            affected_pairs=("driver_id", "size"),
            avg_priority_score=("priority_score", "mean"),
            avg_ghost_rate=("ghost_rate", "mean"),
            flag_reason_vi=("flag_reason_vi", lambda s: s.dropna().iloc[0] if not s.dropna().empty else ""),
        )
        .reset_index()
        .sort_values(["affected_pairs", "avg_priority_score"], ascending=[False, False])
    )


def build_component_summary(flags: pd.DataFrame) -> pd.DataFrame:
    if flags.empty or "component_id" not in flags.columns:
        return pd.DataFrame()
    summary = (
        flags.groupby("component_id", dropna=False)
        .agg(
            flagged_orders=("order_id", "nunique"),
            flagged_drivers=("driver_id", "nunique"),
            flagged_customers=("customer_id", "nunique"),
            top_service=("service_name", lambda s: s.mode().iloc[0] if not s.mode().empty else "Không rõ"),
            top_rule=("business_rule_label", lambda s: s.mode().iloc[0] if not s.mode().empty else "Không rõ"),
            top_rule_story=("business_rule_story", lambda s: s.dropna().iloc[0] if not s.dropna().empty else ""),
            max_priority_score=("priority_score", "max"),
            avg_priority_score=("priority_score", "mean"),
            avg_network_support_score=("network_support_score", "mean"),
            component_size=("component_size", "max"),
            component_edge_count=("component_edge_count", "max"),
            component_density=("component_density", "max"),
        )
        .reset_index()
    )
    pair_counts = (
        flags.groupby("component_id")[["driver_id", "customer_id"]]
        .apply(lambda g: g.drop_duplicates().shape[0])
        .rename("flagged_pairs")
        .reset_index()
    )
    return summary.merge(pair_counts, on="component_id", how="left").sort_values(
        ["component_size", "max_priority_score", "flagged_orders"],
        ascending=[False, False, False],
    )


def build_pair_summary(pairs: pd.DataFrame) -> pd.DataFrame:
    if pairs.empty:
        return pd.DataFrame()
    wanted_columns = [
        "driver_id",
        "customer_id",
        "top_service_name",
        "primary_business_rule_label",
        "primary_business_rule_story",
        "priority_score",
        "ghost_rate",
        "n_trips",
        "component_id",
    ]
    available = [column for column in wanted_columns if column in pairs.columns]
    return pairs[available].sort_values(["priority_score", "n_trips"], ascending=[False, False]).copy()


def build_insight_summary(
    period_summary: pd.DataFrame,
    flags: pd.DataFrame,
    rules: pd.DataFrame,
    components: pd.DataFrame,
) -> dict[str, dict[str, str]]:
    insights: dict[str, dict[str, str]] = {}
    if len(period_summary) >= 2:
        latest = period_summary.iloc[-1]
        previous = period_summary.iloc[-2]
        delta = int(latest["flagged_orders"] - previous["flagged_orders"])
        insights["trend"] = {
            "title": "Biến động gần nhất",
            "value": f"{delta:+,} đơn",
            "detail": f"{'Tăng' if delta >= 0 else 'Giảm'} so với kỳ trước",
        }
    else:
        insights["trend"] = {
            "title": "Biến động gần nhất",
            "value": "Chưa đủ dữ liệu",
            "detail": "Cần ít nhất 2 kỳ để so sánh",
        }

    if not flags.empty and "service_name" in flags.columns:
        top_service = (
            flags.groupby("service_name")["order_id"].nunique().sort_values(ascending=False).reset_index()
        ).iloc[0]
        insights["service"] = {
            "title": "Dịch vụ bị ảnh hưởng nhiều nhất",
            "value": str(top_service["service_name"]),
            "detail": f"{int(top_service['order_id']):,} đơn bị flag",
        }
    else:
        insights["service"] = {"title": "Dịch vụ bị ảnh hưởng nhiều nhất", "value": "Không có dữ liệu", "detail": ""}

    if not rules.empty:
        top_rule = rules.iloc[0]
        insights["rule"] = {
            "title": "Rule nổi bật nhất",
            "value": str(top_rule["business_rule_label"]),
            "detail": str(top_rule["business_rule_story"]),
        }
    else:
        insights["rule"] = {"title": "Rule nổi bật nhất", "value": "Không có dữ liệu", "detail": ""}

    if not components.empty:
        top_component = components.sort_values(
            ["max_priority_score", "component_size", "flagged_orders"],
            ascending=[False, False, False],
        ).iloc[0]
        insights["component"] = {
            "title": "Nhóm WCC cần ưu tiên",
            "value": str(top_component["component_id"]),
            "detail": (
                f"Điểm ưu tiên {top_component['max_priority_score']:.2f} | "
                f"kích thước {int(top_component['component_size'])} | "
                f"{int(top_component['flagged_orders']):,} đơn"
            ),
        }
    else:
        insights["component"] = {"title": "Nhóm WCC cần ưu tiên", "value": "Không có dữ liệu", "detail": ""}

    return insights


def build_cypher_query_pack(row: pd.Series) -> dict[str, str]:
    order_id = repr(str(row.get("order_id", "")))
    customer_id = repr(str(row.get("customer_id", "")))
    driver_id = repr(str(row.get("driver_id", "")))
    business_rule = repr(str(row.get("business_rule_label", "")))
    component_id = repr(str(row.get("component_id", "")))
    return {
        "Cặp tài xế - khách hàng bị flag theo rule": f"""MATCH (c:Customer {{customer_id: {customer_id}}})-[:PLACED]->(o:Order)<-[:SERVED]-(d:Driver {{driver_id: {driver_id}}})
WHERE o.order_id = {order_id}
RETURN c.customer_id AS customer_id,
       d.driver_id AS driver_id,
       o.order_id AS order_id,
       {business_rule} AS fraud_rule,
       o.order_time AS order_time
LIMIT 50;""",
        "Toàn bộ đơn của cặp đang chọn": f"""MATCH (c:Customer {{customer_id: {customer_id}}})-[:PLACED]->(o:Order)<-[:SERVED]-(d:Driver {{driver_id: {driver_id}}})
OPTIONAL MATCH (o)-[:PICKUP_AT]->(pickup:Address)
OPTIONAL MATCH (o)-[:DROPOFF_AT]->(drop:Address)
RETURN c, d, o, pickup, drop
ORDER BY o.order_time DESC
LIMIT 200;""",
        "Các cặp bị flag cùng nhóm WCC": f"""MATCH (d:Driver)-[:SERVED]->(o:Order)<-[:PLACED]-(c:Customer)
WHERE o.order_id IN [
  x IN [] WHERE x IS NOT NULL
]
RETURN d, c, o
LIMIT 0; -- Thay khối này bằng danh sách order_id trong component {component_id}""",
        "Timeline của tài xế đang chọn": f"""MATCH (d:Driver {{driver_id: {driver_id}}})-[:SERVED]->(o:Order)
OPTIONAL MATCH (o)<-[:PLACED]-(c:Customer)
RETURN d, o, c
ORDER BY o.order_time DESC
LIMIT 200;""",
        "Chi tiết order đang chọn": f"""MATCH (o:Order {{order_id: {order_id}}})
OPTIONAL MATCH (o)<-[:PLACED]-(c:Customer)
OPTIONAL MATCH (o)<-[:SERVED]-(d:Driver)
OPTIONAL MATCH (o)-[:PICKUP_AT]->(pickup:Address)
OPTIONAL MATCH (o)-[:DROPOFF_AT]->(drop:Address)
RETURN o, c, d, pickup, drop;""",
    }


def build_component_cypher_query(component_flags: pd.DataFrame, component_id: str) -> str:
    if component_flags.empty or "order_id" not in component_flags.columns:
        return f"// Không có order_id cho nhóm rủi ro {component_id}"
    order_ids = ", ".join(repr(str(order_id)) for order_id in component_flags["order_id"].dropna().astype(str).unique()[:200])
    return f"""MATCH (d:Driver)-[:SERVED]->(o:Order)<-[:PLACED]-(c:Customer)
WHERE o.order_id IN [{order_ids}]
OPTIONAL MATCH (o)-[:PICKUP_AT]->(pickup:Address)
OPTIONAL MATCH (o)-[:DROPOFF_AT]->(drop:Address)
RETURN d, c, o, pickup, drop
LIMIT 500; -- Component {component_id}"""


def _render_metric_cards(metrics: dict[str, int]) -> None:
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Tổng đơn trong tập flagged", f"{metrics['total_orders_in_scope']:,}")
    col2.metric("Đơn bị flag", f"{metrics['flagged_orders']:,}")
    col3.metric("Tài xế bị flag", f"{metrics['flagged_drivers']:,}")
    col4.metric("Khách hàng bị flag", f"{metrics['flagged_customers']:,}")
    col5.metric("Nhóm WCC lớn nhất", f"{metrics['largest_component_size']:,}")


def _render_insight_cards(insights: dict[str, dict[str, str]]) -> None:
    cols = st.columns(4)
    keys = ["trend", "service", "rule", "component"]
    for col, key in zip(cols, keys):
        with col:
            data = insights[key]
            with st.container(border=True):
                st.markdown(f"**{data['title']}**")
                st.markdown(f"### {data['value']}")
                st.caption(data["detail"])


def _render_executive_story(insights: dict[str, dict[str, str]]) -> None:
    st.markdown("### Người xem tổng quan cần nhìn gì hôm nay?")
    st.markdown(
        f"- Theo dõi biến động mới nhất: {insights['trend']['value']} - {insights['trend']['detail']}\n"
        f"- Xem dịch vụ bị ảnh hưởng nhiều nhất: {insights['service']['value']}.\n"
        f"- Hiểu rule nổi bật nhất đang kể câu chuyện gì: {insights['rule']['value']}.\n"
        f"- Ưu tiên nhóm WCC nào cần điều tra trước: {insights['component']['value']}."
    )


def _render_main_trend(summary: pd.DataFrame, granularity_label: str, metric_label: str, chart_key: str) -> None:
    metric_col = METRIC_OPTIONS[metric_label]
    chart = px.line(
        summary,
        x="period_start",
        y=metric_col,
        markers=True,
        line_shape="spline",
        title=f"{metric_label} theo {granularity_label.lower()}",
    )
    chart.update_traces(line=dict(width=4), marker=dict(size=8))
    chart.update_layout(
        xaxis_title=None,
        yaxis_title=metric_label,
        hovermode="x unified",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(chart, width="stretch", key=chart_key)


def _render_executive_tab(
    flags: pd.DataFrame,
    summary: pd.DataFrame,
    rules: pd.DataFrame,
    components: pd.DataFrame,
    granularity_label: str,
) -> None:
    st.subheader("Bức tranh điều hành")
    st.caption("Tab này dành cho người xem tổng quan: cần nhìn ngay xu hướng, dịch vụ chịu ảnh hưởng và rule nổi bật.")

    left, right = st.columns([1.4, 1])
    with left:
        _render_main_trend(summary, granularity_label, "Đơn bị flag", "executive_main_trend")
    with right:
        service_summary = (
            flags.groupby("service_name", dropna=False)
            .agg(flagged_orders=("order_id", "nunique"))
            .reset_index()
            .fillna({"service_name": "Không rõ"})
            .sort_values("flagged_orders", ascending=False)
            .head(10)
        )
        service_chart = px.bar(
            service_summary.sort_values("flagged_orders", ascending=True),
            x="flagged_orders",
            y="service_name",
            orientation="h",
            title="Top dịch vụ theo số đơn bị flag",
        )
        service_chart.update_layout(xaxis_title=None, yaxis_title=None)
        st.plotly_chart(service_chart, width="stretch", key="executive_service_chart")

    left, right = st.columns([1, 1.2])
    with left:
        st.markdown("#### Tổng hợp theo kỳ")
        st.dataframe(
            summary.rename(
                columns={
                    "period_start": "Kỳ bắt đầu",
                    "total_orders_in_scope": "Tổng đơn trong tập flagged",
                    "flagged_orders": "Đơn bị flag",
                    "flagged_drivers": "Tài xế bị flag",
                    "flagged_customers": "Khách hàng bị flag",
                    "flagged_pairs": "Cặp tài xế - khách hàng",
                }
            ),
            width="stretch",
            hide_index=True,
        )
    with right:
        st.markdown("#### Rule fraud nổi bật và câu chuyện")
        if rules.empty:
            st.info("Không có dữ liệu rule fraud.")
        else:
            top_rule_chart = px.bar(
                rules.head(8).sort_values("flagged_orders", ascending=True),
                x="flagged_orders",
                y="business_rule_label",
                orientation="h",
                title="Top rule theo số đơn bị flag",
            )
            top_rule_chart.update_layout(xaxis_title=None, yaxis_title=None)
            st.plotly_chart(top_rule_chart, width="stretch", key="executive_top_rule_chart")
            storytelling_view = rules[
                ["business_rule_label", "business_rule_story", "flagged_orders", "avg_priority_score"]
            ].rename(
                columns={
                    "business_rule_label": "Tên rule",
                    "business_rule_story": "Câu chuyện của rule",
                    "flagged_orders": "Số đơn bị flag",
                    "avg_priority_score": "Điểm ưu tiên trung bình",
                }
            )
            st.dataframe(storytelling_view, width="stretch", hide_index=True)

    if not components.empty:
        st.markdown("#### Nhóm WCC nào cần ưu tiên?")
        component_chart = px.bar(
            components.head(10).sort_values("max_priority_score", ascending=True),
            x="max_priority_score",
            y="component_id",
            orientation="h",
            title="Top nhóm WCC theo điểm ưu tiên",
            hover_data=["component_size", "flagged_orders", "top_service", "top_rule"],
        )
        component_chart.update_layout(xaxis_title=None, yaxis_title=None)
        st.plotly_chart(component_chart, width="stretch", key="executive_component_chart")


def _render_analyst_tab(
    flags: pd.DataFrame,
    pairs: pd.DataFrame,
    reasons: pd.DataFrame,
    summary: pd.DataFrame,
    granularity_label: str,
) -> None:
    st.subheader("Phân tích chuyên sâu cho analyst")
    st.caption("Tab này dành cho analyst: cần soi xu hướng, so sánh dịch vụ/rule và xem cặp đáng nghi nhất.")

    metric_label = st.selectbox("Chỉ số phân tích xu hướng", options=list(METRIC_OPTIONS.keys()), index=0)
    left, right = st.columns([1.2, 1])

    with left:
        _render_main_trend(summary, granularity_label, metric_label, f"analyst_trend_{metric_label}")

    with right:
        breakdown_dimension = st.selectbox(
            "Nhìn theo chiều nào?",
            options=[
                ("Rule fraud", "business_rule_label"),
                ("Dịch vụ", "service_name"),
                ("Mức rủi ro", "risk_tier"),
            ],
            format_func=lambda item: item[0],
        )
        group_col = breakdown_dimension[1]
        breakdown = (
            flags.groupby(group_col, dropna=False)
            .agg(flagged_orders=("order_id", "nunique"))
            .reset_index()
            .fillna({group_col: "Không rõ"})
            .sort_values("flagged_orders", ascending=False)
            .head(10)
        )
        chart = px.bar(
            breakdown.sort_values("flagged_orders", ascending=True),
            x="flagged_orders",
            y=group_col,
            orientation="h",
            title=f"So sánh theo {breakdown_dimension[0].lower()}",
        )
        chart.update_layout(xaxis_title=None, yaxis_title=None)
        st.plotly_chart(chart, width="stretch", key=f"analyst_breakdown_{group_col}")

    left, right = st.columns([1.1, 1])
    with left:
        st.markdown("#### Top cặp tài xế - khách hàng đáng nghi")
        pair_summary = build_pair_summary(pairs)
        if pair_summary.empty:
            st.info("Không có dữ liệu cặp đáng nghi trong bộ lọc hiện tại.")
        else:
            st.dataframe(
                pair_summary.head(20).rename(columns=PAIR_COLUMN_LABELS),
                width="stretch",
                hide_index=True,
            )
    with right:
        st.markdown("#### Lý do bị flag để analyst hiểu")
        if reasons.empty:
            st.info("Không có dữ liệu lý do bị flag.")
        else:
            reason_view = build_reason_overview(reasons).rename(
                columns={
                    "reason_code": "Mã lý do",
                    "affected_pairs": "Số cặp ảnh hưởng",
                    "avg_priority_score": "Điểm ưu tiên trung bình",
                    "avg_ghost_rate": "Tỷ lệ ghost trip trung bình",
                    "flag_reason_vi": "Diễn giải để người xem hiểu",
                }
            )
            st.dataframe(reason_view, width="stretch", hide_index=True)

    st.markdown("#### Analyst cần đọc gì từ tab này?")
    st.markdown(
        "- Xem xu hướng metric chính đang tăng hay giảm.\n"
        "- So sánh dịch vụ, rule và mức rủi ro để biết phần nào chịu tác động lớn nhất.\n"
        "- Đi xuống danh sách cặp đáng nghi để chọn các case cần điều tra tiếp."
    )


def _render_component_tab(components: pd.DataFrame, flags: pd.DataFrame) -> None:
    st.subheader("Điều tra nhóm WCC")
    st.caption("Tab này dành cho investigator: xem nhóm liên kết nào lớn, mạnh và đáng điều tra trước.")
    if components.empty:
        st.info("Không có dữ liệu nhóm WCC trong bộ lọc hiện tại.")
        return

    overview = components[
        [
            "component_id",
            "component_size",
            "flagged_orders",
            "flagged_drivers",
            "flagged_customers",
            "flagged_pairs",
            "max_priority_score",
            "avg_network_support_score",
            "top_service",
            "top_rule",
            "top_rule_story",
        ]
    ].rename(
        columns={
            "component_id": "ID nhóm WCC",
            "component_size": "Kích thước nhóm",
            "flagged_orders": "Đơn bị flag",
            "flagged_drivers": "Tài xế",
            "flagged_customers": "Khách hàng",
            "flagged_pairs": "Cặp",
            "max_priority_score": "Điểm ưu tiên cao nhất",
            "avg_network_support_score": "Điểm hỗ trợ mạng",
            "top_service": "Dịch vụ nổi bật",
            "top_rule": "Rule chính",
            "top_rule_story": "Câu chuyện của rule",
        }
    )
    st.dataframe(overview.head(15), width="stretch", hide_index=True)

    component_ids = components["component_id"].dropna().astype(str).tolist()
    selected_component = st.selectbox("Chọn nhóm WCC để xem chi tiết", options=component_ids)
    component_flags = flags[flags["component_id"].astype(str) == selected_component].copy()
    component_row = components[components["component_id"].astype(str) == selected_component].iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Kích thước nhóm", f"{int(component_row['component_size']):,}")
    c2.metric("Số đơn bị flag", f"{int(component_row['flagged_orders']):,}")
    c3.metric("Số tài xế", f"{int(component_row['flagged_drivers']):,}")
    c4.metric("Số khách hàng", f"{int(component_row['flagged_customers']):,}")

    st.info(
        f"Nhóm WCC này nổi bật ở dịch vụ '{component_row['top_service']}', "
        f"đang được dẫn bởi rule '{component_row['top_rule']}'. "
        f"Câu chuyện chính: {component_row['top_rule_story']}"
    )

    detail_columns = [
        column
        for column in [
            "order_id",
            "order_date",
            "driver_id",
            "customer_id",
            "service_name",
            "business_rule_label",
            "priority_score",
            "network_support_score",
            "component_size",
            "risk_tier",
            "business_rule_story",
        ]
        if column in component_flags.columns
    ]
    st.dataframe(
        component_flags[detail_columns].sort_values("priority_score", ascending=False).rename(columns=DETAIL_COLUMN_LABELS),
        width="stretch",
        hide_index=True,
    )

    st.markdown("#### Cypher mẫu cho nhóm WCC này")
    st.code(build_component_cypher_query(component_flags, str(selected_component)), language="cypher")


def _render_case_tab(flags: pd.DataFrame) -> None:
    st.subheader("Điều tra case")
    st.caption("Tab này dành cho investigator cần xem rõ từng case, hiểu câu chuyện và lấy Cypher để visualize trên Neo4j.")
    if flags.empty:
        st.info("Không có dữ liệu case trong bộ lọc hiện tại.")
        return

    detail_columns = [
        column
        for column in [
            "order_id",
            "order_date",
            "driver_id",
            "customer_id",
            "service_name",
            "business_rule_label",
            "reason_code",
            "priority_score",
            "ghost_rate",
            "n_trips",
            "component_id",
            "component_size",
            "risk_tier",
            "business_rule_story",
            "flag_reason_vi",
            "supporting_signal_vi",
        ]
        if column in flags.columns
    ]
    detail_frame = flags[detail_columns].sort_values(["priority_score", "order_date"], ascending=[False, False]).copy()

    st.dataframe(
        detail_frame.rename(columns=DETAIL_COLUMN_LABELS),
        width="stretch",
        hide_index=True,
    )

    selected_order_id = st.selectbox(
        "Chọn một đơn bị flag để xem câu chuyện case",
        options=detail_frame["order_id"].astype(str).unique().tolist(),
    )
    selected_row = detail_frame[detail_frame["order_id"].astype(str) == selected_order_id].iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Dịch vụ", str(selected_row.get("service_name", "Không rõ")))
    c2.metric("Rule chính", str(selected_row.get("business_rule_label", "Không rõ")))
    c3.metric("Mức rủi ro", str(selected_row.get("risk_tier", "Không rõ")))
    c4.metric("Điểm ưu tiên", f"{float(selected_row.get('priority_score', 0)):.2f}")

    st.info(f"Câu chuyện của case: {selected_row.get('business_rule_story', 'Chưa có diễn giải.')}")
    st.markdown(
        f"- **Vì sao case bị flag:** {selected_row.get('flag_reason_vi', 'Chưa có diễn giải')}\n"
        f"- **Tín hiệu hỗ trợ:** {selected_row.get('supporting_signal_vi', 'Chưa có diễn giải')}\n"
        f"- **Nhóm WCC liên quan:** {selected_row.get('component_id', 'Không rõ')}"
    )

    cypher_pack = build_cypher_query_pack(selected_row)
    query_name = st.selectbox("Chọn loại truy vấn Neo4j", options=list(cypher_pack.keys()))
    if query_name == "Các cặp bị flag cùng nhóm WCC":
        component_id = str(selected_row.get("component_id", ""))
        component_flags = flags[flags["component_id"].astype(str) == component_id].copy()
        st.code(build_component_cypher_query(component_flags, component_id), language="cypher")
    else:
        st.code(cypher_pack[query_name], language="cypher")


def render_dashboard() -> None:
    st.set_page_config(page_title="Dashboard Fraud KB-C", layout="wide")
    st.title("Dashboard Fraud KB-C")
    st.caption(
        "Dashboard này được sắp theo 3 lớp sử dụng: "
        "người xem tổng quan, analyst cần phân tích sâu và investigator cần điều tra case."
    )

    reports = load_reports(str(REPORT_DIR))
    flags = _normalize_flags(reports["flags"])
    pairs = _normalize_pairs(reports["pairs"])
    reasons = _normalize_reasons(reports["reasons"])

    if flags.empty:
        st.warning("Không tìm thấy dữ liệu `flagged_orders.parquet` để dựng dashboard.")
        return

    filters = _render_filters(flags)
    filtered_flags, filtered_pairs, filtered_reasons = _apply_filters(flags, pairs, reasons, filters)
    if filtered_flags.empty:
        st.warning("Không có dữ liệu trong bộ lọc hiện tại.")
        return

    granularity_label = st.radio("Chu kỳ tổng hợp", options=list(GRANULARITY_CONFIG.keys()), horizontal=True)
    period_col = GRANULARITY_CONFIG[granularity_label]

    metrics = build_overview_metrics(filtered_flags)
    period_summary = build_period_summary(filtered_flags, period_col)
    rule_overview = build_rule_overview(filtered_flags)
    component_summary = build_component_summary(filtered_flags)
    insights = build_insight_summary(period_summary, filtered_flags, rule_overview, component_summary)

    _render_metric_cards(metrics)
    _render_insight_cards(insights)
    _render_executive_story(insights)
    st.caption(
        "Lưu ý: nguồn hiện tại là tập đơn đã bị flag, nên 'Tổng đơn trong tập flagged' "
        "không phải tổng số đơn của toàn hệ thống."
    )

    executive_tab, analyst_tab, component_tab, case_tab = st.tabs(
        ["1. Điều hành", "2. Phân tích chuyên sâu", "3. Điều tra nhóm WCC", "4. Điều tra case"]
    )

    with executive_tab:
        _render_executive_tab(filtered_flags, period_summary, rule_overview, component_summary, granularity_label)

    with analyst_tab:
        _render_analyst_tab(filtered_flags, filtered_pairs, filtered_reasons, period_summary, granularity_label)

    with component_tab:
        _render_component_tab(component_summary, filtered_flags)

    with case_tab:
        _render_case_tab(filtered_flags)


if __name__ == "__main__":
    render_dashboard()
