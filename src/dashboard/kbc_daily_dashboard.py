"""KB-C daily fraud dashboard."""

from __future__ import annotations

from html import escape
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


REPORT_DIR = Path("reports/task3")
ALL_OPTION = "__all__"
EXECUTIVE_CARD_HEIGHT = 360
EXECUTIVE_CHART_MARGIN = dict(l=24, r=16, t=56, b=48)
TABLE_HEIGHT = 360
BLUE_SCALE = ["#2563EB", "#3B82F6", "#60A5FA", "#93C5FD", "#BFDBFE"]

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
    "order_id": "Mã đơn",
    "complete_time_local_tz": "Ngày hoàn thành",
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


def _inject_dashboard_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bg-app: #F7F8FA;
            --card-bg: #FFFFFF;
            --card-border: #E5E7EB;
            --text-primary: #1F2937;
            --text-secondary: #4B5563;
            --text-muted: #6B7280;
            --primary: #2563EB;
            --primary-soft: #3B82F6;
            --primary-light: #EFF6FF;
            --cyan: #12B5CB;
            --purple: #8B5CF6;
            --orange: #F59E0B;
            --shadow-soft: 0 1px 3px rgba(15, 23, 42, 0.04);
        }

        .stApp {
            background: var(--bg-app);
        }

        .block-container {
            max-width: 1440px;
            padding-top: 1rem;
            padding-bottom: 2.25rem;
        }

        h1, h2, h3 {
            color: var(--text-primary);
            letter-spacing: -0.03em;
        }

        [data-testid="stVerticalBlockBorderWrapper"] {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 18px;
            box-shadow: var(--shadow-soft);
            padding: 0.25rem;
        }

        [data-testid="stMetric"] {
            background: transparent;
            border: none;
            padding: 0;
        }

        .dashboard-stat-card,
        .dashboard-insight-card,
        .dashboard-rule-card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 18px;
            box-shadow: var(--shadow-soft);
        }

        .dashboard-stat-card {
            padding: 20px 20px 18px;
            min-height: 132px;
        }

        .dashboard-insight-card {
            padding: 16px 20px 18px;
            min-height: 196px;
        }

        .dashboard-rule-card {
            padding: 18px 20px;
            margin-bottom: 12px;
        }

        .stat-top,
        .insight-top,
        .rule-top {
            display: flex;
            align-items: center;
            gap: 14px;
        }

        .icon-badge {
            width: 46px;
            height: 46px;
            border-radius: 16px;
            background: linear-gradient(180deg, #F8FBFF 0%, #ECF5FF 100%);
            border: 1px solid #DCEBFF;
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--primary);
            font-size: 22px;
            font-weight: 700;
            flex: 0 0 auto;
        }

        .stat-title,
        .insight-title,
        .rule-title {
            font-size: 14px;
            line-height: 1.45;
            color: var(--text-secondary);
            font-weight: 600;
        }

        .stat-value,
        .insight-value {
            margin-top: 14px;
            color: var(--text-primary);
            font-size: 18px;
            line-height: 1.25;
            font-weight: 700;
            letter-spacing: -0.02em;
        }

        .stat-value {
            font-size: 20px;
            line-height: 1.15;
        }

        .stat-subtitle,
        .insight-detail,
        .rule-detail {
            margin-top: 8px;
            color: var(--text-muted);
            font-size: 13px;
            line-height: 1.5;
        }

        .insight-detail {
            display: -webkit-box;
            -webkit-line-clamp: 3;
            -webkit-box-orient: vertical;
            overflow: hidden;
            min-height: 58px;
        }

        .insight-accent {
            width: 44px;
            height: 4px;
            border-radius: 999px;
            margin-bottom: 14px;
        }

        .rule-grid {
            display: grid;
            grid-template-columns: minmax(0, 1.7fr) 160px 160px 22px;
            gap: 16px;
            align-items: center;
        }

        .rule-metric-label {
            color: var(--text-muted);
            font-size: 12px;
            margin-bottom: 4px;
        }

        .rule-metric-value {
            color: var(--primary);
            font-size: 18px;
            line-height: 1.1;
            font-weight: 700;
        }

        .rule-chevron {
            color: #94A3B8;
            font-size: 24px;
            text-align: right;
        }

        .hero-card .stRadio > div {
            margin-top: 2px;
        }

        .stDateInput label,
        .stSelectbox label,
        .stRadio label {
            color: var(--text-secondary);
            font-size: 14px;
            font-weight: 600;
        }

        .stDateInput > div,
        .stSelectbox > div > div {
            background: #FFFFFF;
            border-radius: 12px;
        }

        .hero-card [data-testid="stRadio"] > div {
            gap: 0.75rem;
        }

        .hero-card [data-testid="stRadio"] label {
            background: #FFFFFF;
            border: 1px solid #DCE6F3;
            border-radius: 999px;
            padding: 8px 14px 8px 10px;
            min-height: 40px;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: all 0.15s ease;
        }

        .hero-card [data-testid="stRadio"] label:hover {
            border-color: #BFD6FF;
            background: #F8FBFF;
        }

        .hero-card [data-testid="stRadio"] label:has(input:checked) {
            background: #EFF6FF;
            border-color: #BFDBFE;
            box-shadow: inset 0 0 0 1px rgba(37, 99, 235, 0.08);
        }

        .hero-card [data-testid="stRadio"] label p {
            margin: 0;
            color: var(--text-secondary);
            font-weight: 600;
        }

        .hero-card [data-testid="stRadio"] label:has(input:checked) p {
            color: var(--primary);
        }

        .hero-card [data-testid="stRadio"] input {
            accent-color: #2563EB;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 2rem;
            border-bottom: 1px solid var(--card-border);
            padding-bottom: 0;
        }

        .stTabs [data-baseweb="tab"] {
            background: transparent;
            border: none;
            color: var(--text-secondary);
            border-bottom: 2px solid transparent;
            height: 44px;
            border-radius: 0;
            padding: 0;
            font-weight: 600;
        }

        .stTabs [aria-selected="true"] {
            color: var(--primary);
            border-bottom-color: var(--primary);
            background: transparent;
        }

        .stTabs [data-baseweb="tab"]:hover {
            color: var(--primary);
            background: transparent;
        }

        [data-testid="stDataFrame"] {
            border-radius: 16px;
            overflow: hidden;
        }

        .stCodeBlock {
            border: 1px solid var(--card-border);
            border-radius: 16px;
        }

        div[data-testid="column"] > div:has(.dashboard-stat-card),
        div[data-testid="column"] > div:has(.dashboard-insight-card) {
            height: 100%;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _format_period_value(value: object) -> str:
    if pd.isna(value):
        return ""
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return str(value)
    return ts.strftime("%d/%m/%Y")


def _prepare_table(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    view = frame.copy()
    for column in view.columns:
        lowered = str(column).lower()
        if "date" in lowered or "period" in lowered:
            view[column] = view[column].apply(_format_period_value)
    return view


def _show_table(frame: pd.DataFrame, *, height: int = TABLE_HEIGHT) -> None:
    st.dataframe(_prepare_table(frame), width="stretch", height=height, hide_index=True)


def _style_plotly_chart(
    fig,
    *,
    height: int | None = None,
    xaxis_title: str | None = None,
    yaxis_title: str | None = None,
) -> None:
    fig.update_layout(
        height=height,
        margin=EXECUTIVE_CHART_MARGIN,
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#FFFFFF", bordercolor="#DBEAFE", font=dict(color="#1F2937")),
        font=dict(color="#4B5563"),
        title_font=dict(size=18, color="#1F2937"),
        xaxis_title=xaxis_title,
        yaxis_title=yaxis_title,
    )
    fig.update_xaxes(
        showgrid=False,
        zeroline=False,
        linecolor="#E5E7EB",
        tickfont=dict(color="#6B7280"),
        title_font=dict(color="#6B7280"),
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor="#E5E7EB",
        gridwidth=1,
        zeroline=False,
        tickfont=dict(color="#6B7280"),
        title_font=dict(color="#6B7280"),
    )


def _render_stat_card(title: str, value: str, icon: str, subtitle: str = "") -> None:
    st.markdown(
        f"""
        <div class="dashboard-stat-card">
            <div class="stat-top">
                <div class="icon-badge">{escape(icon)}</div>
                <div class="stat-title">{escape(title)}</div>
            </div>
            <div class="stat-value">{escape(value)}</div>
            <div class="stat-subtitle">{escape(subtitle)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_insight_card(title: str, value: str, detail: str, icon: str, accent: str) -> None:
    st.markdown(
        f"""
        <div class="dashboard-insight-card">
            <div class="insight-accent" style="background:{accent};"></div>
            <div class="insight-top">
                <div class="icon-badge">{escape(icon)}</div>
                <div class="insight-title">{escape(title)}</div>
            </div>
            <div class="insight-value">{escape(value)}</div>
            <div class="insight-detail">{escape(detail)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_rule_story_card(
    title: str,
    detail: str,
    flagged_orders: str,
    avg_priority: str,
    icon: str,
) -> None:
    st.markdown(
        f"""
        <div class="dashboard-rule-card">
            <div class="rule-grid">
                <div class="rule-top">
                    <div class="icon-badge">{escape(icon)}</div>
                    <div>
                        <div class="rule-title">{escape(title)}</div>
                        <div class="rule-detail">{escape(detail)}</div>
                    </div>
                </div>
                <div>
                    <div class="rule-metric-label">Đơn bị flag</div>
                    <div class="rule-metric-value">{escape(flagged_orders)}</div>
                </div>
                <div>
                    <div class="rule-metric-label">Điểm ưu tiên TB</div>
                    <div class="rule-metric-value">{escape(avg_priority)}</div>
                </div>
                <div class="rule-chevron">›</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


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

    col1, col2, col3, col4 = st.columns([1.15, 1, 1, 1])
    with col1:
        date_range = st.date_input(
            "Khoảng ngày",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
            format="YYYY/MM/DD",
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
        start_date, end_date = date_range if len(date_range) == 2 else (date_range[0], date_range[0])
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
    start_date = pd.Timestamp(filters["start_date"]).normalize()
    end_date = pd.Timestamp(filters["end_date"]).normalize()
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
    return (
        summary.merge(pair_counts, on=period_col, how="left")
        .rename(columns={period_col: "period_start"})
        .sort_values("period_start")
    )


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
    component_summary = summary.merge(pair_counts, on="component_id", how="left").sort_values(
        ["component_size", "max_priority_score", "flagged_orders"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    component_summary["component_display_id"] = [f"WCC-{index:03d}" for index in range(1, len(component_summary) + 1)]
    return component_summary


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
            "icon": "↗",
            "accent": "#2563EB",
        }
    else:
        insights["trend"] = {
            "title": "Biến động gần nhất",
            "value": "Chưa đủ dữ liệu",
            "detail": "Cần ít nhất 2 kỳ để so sánh",
            "icon": "↗",
            "accent": "#2563EB",
        }

    if not flags.empty and "service_name" in flags.columns:
        top_service = (
            flags.groupby("service_name")["order_id"].nunique().sort_values(ascending=False).reset_index().iloc[0]
        )
        insights["service"] = {
            "title": "Dịch vụ bị ảnh hưởng nhiều nhất",
            "value": str(top_service["service_name"]),
            "detail": f"{int(top_service['order_id']):,} đơn bị flag",
            "icon": "◔",
            "accent": "#12B5CB",
        }
    else:
        insights["service"] = {
            "title": "Dịch vụ bị ảnh hưởng nhiều nhất",
            "value": "Không có dữ liệu",
            "detail": "",
            "icon": "◔",
            "accent": "#12B5CB",
        }

    if not rules.empty:
        top_rule = rules.iloc[0]
        insights["rule"] = {
            "title": "Rule nổi bật nhất",
            "value": str(top_rule["business_rule_label"]),
            "detail": str(top_rule["business_rule_story"]),
            "icon": "⛨",
            "accent": "#8B5CF6",
        }
    else:
        insights["rule"] = {
            "title": "Rule nổi bật nhất",
            "value": "Không có dữ liệu",
            "detail": "",
            "icon": "⛨",
            "accent": "#8B5CF6",
        }

    if not components.empty:
        top_component = components.sort_values(
            ["max_priority_score", "component_size", "flagged_orders"],
            ascending=[False, False, False],
        ).iloc[0]
        insights["component"] = {
            "title": "Nhóm WCC cần ưu tiên",
            "value": str(top_component.get("component_display_id", top_component["component_id"])),
            "detail": (
                f"Điểm ưu tiên {top_component['max_priority_score']:.2f}  |  "
                f"kích thước {int(top_component['component_size'])}  |  "
                f"{int(top_component['flagged_orders']):,} đơn"
            ),
            "icon": "◎",
            "accent": "#F59E0B",
        }
    else:
        insights["component"] = {
            "title": "Nhóm WCC cần ưu tiên",
            "value": "Không có dữ liệu",
            "detail": "",
            "icon": "◎",
            "accent": "#F59E0B",
        }

    return insights


def build_cypher_query_pack(row: pd.Series) -> dict[str, str]:
    order_id = repr(str(row.get("order_id", "")))
    customer_id = repr(str(row.get("customer_id", "")))
    driver_id = repr(str(row.get("driver_id", "")))
    business_rule = repr(str(row.get("business_rule_label", "")))
    component_id = repr(str(row.get("component_id", "")))
    return {
        "Cặp tài xế - khách hàng bị gắn cờ": f"""// Visualize đúng cặp driver-customer đang bị gắn cờ.
MATCH p_flagged_pair = (c_flagged:Customer {{customer_id: {customer_id}}})-[:PLACED]->(o_flagged:Order)<-[:SERVED]-(d_flagged:Driver {{driver_id: {driver_id}}})
RETURN p_flagged_pair AS graph_path;""",
        "Các tài xế liên quan tới customer bị gắn cờ": f"""// Visualize các tài xế khác từng phục vụ customer đang nằm trong cặp flagged.
MATCH p_related_drivers = (c_flagged:Customer {{customer_id: {customer_id}}})-[:PLACED]->(o_related_driver:Order)<-[:SERVED]-(d_related:Driver)
WHERE d_related.driver_id <> {driver_id}
RETURN p_related_drivers AS graph_path;""",
        "Các khách hàng liên quan tới driver bị gắn cờ": f"""// Visualize các khách hàng khác từng đi với driver đang nằm trong cặp flagged.
MATCH p_related_customers = (d_flagged:Driver {{driver_id: {driver_id}}})-[:SERVED]->(o_related_customer:Order)<-[:PLACED]-(c_related:Customer)
WHERE c_related.customer_id <> {customer_id}
RETURN p_related_customers AS graph_path;""",
        "2 tài xế bị flag và khách hàng chung/riêng": f"""// Mục tiêu: chỉ hiển thị 2 tài xế bị gắn flag và các khách hàng
// chung / riêng của 2 tài xế đó, để Browser nhìn graph đơn giản hơn.
// Driver 1 lấy từ case đang chọn. Hãy thay DRIVER_ID_2 bằng tài xế thứ hai bạn muốn so sánh.
WITH {driver_id} AS driver_id_1, 'DRIVER_ID_2' AS driver_id_2
MATCH (d1:Driver {{driver_id: driver_id_1}})
MATCH (d2:Driver {{driver_id: driver_id_2}})
MATCH p = (c:Customer)-[:PLACED]->(o:Order)
          <-[:SERVED]-(d:Driver)
WHERE d.driver_id IN [driver_id_1, driver_id_2]
  AND EXISTS {{
    MATCH (c)-[:PLACED]->(:Order)<-[:SERVED]-(:Driver {{driver_id: driver_id_1}})
  }}
  AND EXISTS {{
    MATCH (c)-[:PLACED]->(:Order)<-[:SERVED]-(:Driver {{driver_id: driver_id_2}})
  }}
RETURN p AS graph_path
UNION
WITH {driver_id} AS driver_id_1, 'DRIVER_ID_2' AS driver_id_2
MATCH p = (c:Customer)-[:PLACED]->(o:Order)<-[:SERVED]-(d:Driver {{driver_id: driver_id_1}})
WHERE NOT EXISTS {{
    MATCH (c)-[:PLACED]->(:Order)<-[:SERVED]-(:Driver {{driver_id: driver_id_2}})
}}
RETURN p AS graph_path
UNION
WITH {driver_id} AS driver_id_1, 'DRIVER_ID_2' AS driver_id_2
MATCH p = (c:Customer)-[:PLACED]->(o:Order)<-[:SERVED]-(d:Driver {{driver_id: driver_id_2}})
WHERE NOT EXISTS {{
    MATCH (c)-[:PLACED]->(:Order)<-[:SERVED]-(:Driver {{driver_id: driver_id_1}})
}}
RETURN p AS graph_path;""",
        "Khách hàng chung giữa driver flagged và driver liên quan": f"""// Visualize các customer giao cắt giữa driver flagged và những driver khác
// cũng từng phục vụ customer của cặp flagged. Hữu ích để soi common cluster / WCC.
MATCH (c_flagged:Customer {{customer_id: {customer_id}}})-[:PLACED]->(:Order)<-[:SERVED]-(d_related:Driver)
WHERE d_related.driver_id <> {driver_id}
MATCH p_shared_customers = (d_flagged:Driver {{driver_id: {driver_id}}})-[:SERVED]->(o_left:Order)<-[:PLACED]-(c_shared:Customer)-[:PLACED]->(o_right:Order)<-[:SERVED]-(d_related)
WHERE c_shared.customer_id <> {customer_id}
RETURN p_shared_customers AS graph_path;""",
        "Case graph: đơn flagged và hạ tầng liên quan": f"""// Mục tiêu: mở case graph của đúng 1 order bị flag để analyst/investigator nhìn
// ngay ai tham gia, order nằm ở service nào và đi qua hạ tầng nào.
MATCH p_core = (c:Customer {{customer_id: {customer_id}}})-[:PLACED]->(o:Order {{order_id: {order_id}}})<-[:SERVED]-(d:Driver {{driver_id: {driver_id}}})
RETURN p_core AS graph_path
UNION
MATCH p_pickup = (o:Order {{order_id: {order_id}}})-[:PICKUP_AT]->(:Address)
RETURN p_pickup AS graph_path
UNION
MATCH p_dropoff = (o:Order {{order_id: {order_id}}})-[:DROPOFF_AT]->(:Address)
RETURN p_dropoff AS graph_path
UNION
MATCH p_payment = (o:Order {{order_id: {order_id}}})-[:PAID_BY]->(:PaymentMethod)
RETURN p_payment AS graph_path
UNION
MATCH p_promo = (o:Order {{order_id: {order_id}}})-[:USED_PROMO]->(:PromotionCode)
RETURN p_promo AS graph_path
UNION
MATCH p_campaign = (o:Order {{order_id: {order_id}}})-[:USED_PROMO]->(:PromotionCode)-[:IN_CAMPAIGN]->(:PromotionCampaign)
RETURN p_campaign AS graph_path
UNION
MATCH p_service = (o:Order {{order_id: {order_id}}})-[:USES_SERVICE]->(:RideService)
RETURN p_service AS graph_path
UNION
MATCH p_cancel_actor = (o:Order {{order_id: {order_id}}})-[:CANCELLED_BY]->(:CancelActor)
RETURN p_cancel_actor AS graph_path
UNION
MATCH p_cancel_reason = (o:Order {{order_id: {order_id}}})-[:HAS_CANCEL_REASON]->(:CancelReason)
RETURN p_cancel_reason AS graph_path;""",
        "Pair graph: toàn bộ lịch sử của cặp": f"""// Mục tiêu: visualize full order-history của 1 cặp driver-customer bị nghi ngờ,
// để xem mật độ lặp lại, reuse hạ tầng và độ tập trung hành vi.
MATCH p_core = (c:Customer {{customer_id: {customer_id}}})-[:PLACED]->(o:Order)<-[:SERVED]-(d:Driver {{driver_id: {driver_id}}})
RETURN p_core AS graph_path
UNION
MATCH p_pickup = (c:Customer {{customer_id: {customer_id}}})-[:PLACED]->(o:Order)<-[:SERVED]-(d:Driver {{driver_id: {driver_id}}}),
                 (o)-[:PICKUP_AT]->(:Address)
RETURN p_pickup AS graph_path
UNION
MATCH p_dropoff = (c:Customer {{customer_id: {customer_id}}})-[:PLACED]->(o:Order)<-[:SERVED]-(d:Driver {{driver_id: {driver_id}}}),
                  (o)-[:DROPOFF_AT]->(:Address)
RETURN p_dropoff AS graph_path
UNION
MATCH p_payment = (c:Customer {{customer_id: {customer_id}}})-[:PLACED]->(o:Order)<-[:SERVED]-(d:Driver {{driver_id: {driver_id}}}),
                  (o)-[:PAID_BY]->(:PaymentMethod)
RETURN p_payment AS graph_path
UNION
MATCH p_promo = (c:Customer {{customer_id: {customer_id}}})-[:PLACED]->(o:Order)<-[:SERVED]-(d:Driver {{driver_id: {driver_id}}}),
                (o)-[:USED_PROMO]->(:PromotionCode)
RETURN p_promo AS graph_path
;""",
        "Shared infrastructure quanh cặp nghi ngờ": f"""// Mục tiêu: nhìn các order/actor khác reuse cùng pickup, dropoff, payment, promo
// với cặp đang điều tra. Query này hữu ích để phát hiện fraud ring / farm / reuse infra.
MATCH (:Customer {{customer_id: {customer_id}}})-[:PLACED]->(seed:Order)<-[:SERVED]-(:Driver {{driver_id: {driver_id}}})
WITH collect(DISTINCT seed) AS seed_orders
UNWIND seed_orders AS so
MATCH p1 = (so)-[:PICKUP_AT]->(a:Address)<-[:PICKUP_AT]-(other_pickup:Order)<-[:PLACED]-(:Customer)
WHERE other_pickup <> so
RETURN p1 AS graph_path
UNION
MATCH (:Customer {{customer_id: {customer_id}}})-[:PLACED]->(seed:Order)<-[:SERVED]-(:Driver {{driver_id: {driver_id}}})
WITH collect(DISTINCT seed) AS seed_orders
UNWIND seed_orders AS so
MATCH p2 = (so)-[:DROPOFF_AT]->(a:Address)<-[:DROPOFF_AT]-(other_dropoff:Order)<-[:PLACED]-(:Customer)
WHERE other_dropoff <> so
RETURN p2 AS graph_path
UNION
MATCH (:Customer {{customer_id: {customer_id}}})-[:PLACED]->(seed:Order)<-[:SERVED]-(:Driver {{driver_id: {driver_id}}})
WITH collect(DISTINCT seed) AS seed_orders
UNWIND seed_orders AS so
MATCH p3 = (so)-[:PAID_BY]->(pm:PaymentMethod)<-[:PAID_BY]-(other_payment:Order)<-[:PLACED]-(:Customer)
WHERE other_payment <> so
RETURN p3 AS graph_path
UNION
MATCH (:Customer {{customer_id: {customer_id}}})-[:PLACED]->(seed:Order)<-[:SERVED]-(:Driver {{driver_id: {driver_id}}})
WITH collect(DISTINCT seed) AS seed_orders
UNWIND seed_orders AS so
MATCH p4 = (so)-[:USED_PROMO]->(promo:PromotionCode)<-[:USED_PROMO]-(other_promo:Order)<-[:PLACED]-(:Customer)
WHERE other_promo <> so
RETURN p4 AS graph_path;""",
        "Lân cận của tài xế đang chọn": f"""// Mục tiêu: xem tài xế này kết nối với những customer/order nào khác,
// để đánh giá mức độ tập trung bất thường quanh cùng một customer hay một cụm customer nhỏ.
MATCH p = (d:Driver {{driver_id: {driver_id}}})-[:SERVED]->(o:Order)<-[:PLACED]-(c:Customer)
RETURN p AS graph_path
UNION
MATCH p = (d:Driver {{driver_id: {driver_id}}})-[:SERVED]->(o:Order)-[:USES_SERVICE]->(:RideService)
RETURN p AS graph_path
UNION
MATCH p = (d:Driver {{driver_id: {driver_id}}})-[:SERVED]->(o:Order)-[:PICKUP_AT]->(:Address)
RETURN p AS graph_path
UNION
MATCH p = (d:Driver {{driver_id: {driver_id}}})-[:SERVED]->(o:Order)-[:DROPOFF_AT]->(:Address)
RETURN p AS graph_path;""",
        "Chi tiết order đang chọn": f"""// Mục tiêu: graph drill-down cho 1 order cụ thể, phù hợp lúc analyst muốn bấm sâu
// vào một case và xác định đầy đủ context để xuất phát điều tra.
MATCH p1 = (c:Customer)-[:PLACED]->(o:Order {{order_id: {order_id}}})<-[:SERVED]-(d:Driver)
RETURN p1 AS graph_path
UNION
MATCH p2 = (o:Order {{order_id: {order_id}}})-[:PICKUP_AT]->(:Address)
RETURN p2 AS graph_path
UNION
MATCH p3 = (o:Order {{order_id: {order_id}}})-[:DROPOFF_AT]->(:Address)
RETURN p3 AS graph_path
UNION
MATCH p4 = (o:Order {{order_id: {order_id}}})-[:PAID_BY]->(:PaymentMethod)
RETURN p4 AS graph_path
UNION
MATCH p5 = (o:Order {{order_id: {order_id}}})-[:USED_PROMO]->(:PromotionCode)
RETURN p5 AS graph_path;""",
    }


def build_component_cypher_query(component_flags: pd.DataFrame, component_id: str) -> str:
    if component_flags.empty or "order_id" not in component_flags.columns:
        return f"// Không có order_id cho nhóm rủi ro {component_id}"
    order_ids = ", ".join(repr(str(order_id)) for order_id in component_flags["order_id"].dropna().astype(str).unique()[:200])
    return f"""// Mục tiêu: mở toàn bộ graph của 1 WCC/component nghi ngờ để visualize cluster,
// không chỉ xem order list. Query trả về core graph + shared infra bên trong component.
WITH [{order_ids}] AS order_ids
MATCH p_core = (c:Customer)-[:PLACED]->(o:Order)<-[:SERVED]-(d:Driver)
WHERE o.order_id IN order_ids
RETURN p_core AS graph_path
UNION
WITH [{order_ids}] AS order_ids
MATCH p_pickup = (o1:Order)-[:PICKUP_AT]->(a:Address)<-[:PICKUP_AT]-(o2:Order)
WHERE o1.order_id IN order_ids
  AND o2.order_id IN order_ids
  AND o1.order_id < o2.order_id
RETURN p_pickup AS graph_path
UNION
WITH [{order_ids}] AS order_ids
MATCH p_dropoff = (o1:Order)-[:DROPOFF_AT]->(a:Address)<-[:DROPOFF_AT]-(o2:Order)
WHERE o1.order_id IN order_ids
  AND o2.order_id IN order_ids
  AND o1.order_id < o2.order_id
RETURN p_dropoff AS graph_path
UNION
WITH [{order_ids}] AS order_ids
MATCH p_payment = (o1:Order)-[:PAID_BY]->(pm:PaymentMethod)<-[:PAID_BY]-(o2:Order)
WHERE o1.order_id IN order_ids
  AND o2.order_id IN order_ids
  AND o1.order_id < o2.order_id
RETURN p_payment AS graph_path
UNION
WITH [{order_ids}] AS order_ids
MATCH p_promo = (o1:Order)-[:USED_PROMO]->(promo:PromotionCode)<-[:USED_PROMO]-(o2:Order)
WHERE o1.order_id IN order_ids
  AND o2.order_id IN order_ids
  AND o1.order_id < o2.order_id
RETURN p_promo AS graph_path
LIMIT 800; // Component {component_id}"""


def _render_header_and_filters(flags: pd.DataFrame) -> dict[str, object]:
    with st.container(border=True):
        st.markdown('<div class="hero-card">', unsafe_allow_html=True)
        st.title("Dashboard Fraud KB-C")
        st.caption(
            "Dashboard này được sắp theo 3 lớp sử dụng: người xem tổng quan, analyst cần phân tích sâu và investigator cần điều tra case."
        )
        filters = _render_filters(flags)
        st.radio("Chu kỳ tổng hợp", options=list(GRANULARITY_CONFIG.keys()), horizontal=True, key="granularity_radio")
        st.markdown("</div>", unsafe_allow_html=True)
    return filters


def _render_metric_cards(metrics: dict[str, int]) -> None:
    cards = [
        ("Tổng đơn trong tập flagged", f"{metrics['total_orders_in_scope']:,}", "◫"),
        ("Đơn bị flag", f"{metrics['flagged_orders']:,}", "⚑"),
        ("Tài xế bị flag", f"{metrics['flagged_drivers']:,}", "◌"),
        ("Khách hàng bị flag", f"{metrics['flagged_customers']:,}", "◍"),
        ("Nhóm WCC lớn nhất", f"{metrics['largest_component_size']:,}", "◎"),
    ]
    cols = st.columns(5)
    for col, card in zip(cols, cards):
        with col:
            _render_stat_card(card[0], card[1], card[2])
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)


def _render_insight_cards(insights: dict[str, dict[str, str]]) -> None:
    cols = st.columns(4)
    for col, key in zip(cols, ["trend", "service", "rule", "component"]):
        with col:
            data = insights[key]
            _render_insight_card(
                title=data["title"],
                value=data["value"],
                detail=data["detail"],
                icon=data["icon"],
                accent=data["accent"],
            )


def _render_rule_story_overview(rules: pd.DataFrame) -> None:
    with st.container(border=True):
        st.markdown("### Câu chuyện của các rules")
        st.caption(
            "Khối này tổng hợp nhanh câu chuyện chung của các rule để người xem hiểu bức tranh tổng quan trước khi xuống bảng chi tiết."
        )
        if rules.empty:
            st.info("Không có dữ liệu rule fraud.")
            return

        icons = ["⛨", "◉", "∞", "⌂"]
        for index, (_, row) in enumerate(rules.head(4).iterrows()):
            _render_rule_story_card(
                title=str(row["business_rule_label"]),
                detail=str(row.get("business_rule_story", "")),
                flagged_orders=f"{int(row['flagged_orders']):,}",
                avg_priority=f"{float(row['avg_priority_score']):.2f}",
                icon=icons[index % len(icons)],
            )


def _render_main_trend(
    summary: pd.DataFrame,
    granularity_label: str,
    metric_label: str,
    chart_key: str,
    chart_height: int | None = None,
) -> None:
    metric_col = METRIC_OPTIONS[metric_label]
    chart = px.line(
        summary,
        x="period_start",
        y=metric_col,
        markers=True,
        line_shape="spline",
        title=f"{metric_label} theo {granularity_label.lower()}",
    )
    chart.update_traces(
        line=dict(width=4, color="#2563EB"),
        marker=dict(size=8, color="#2563EB", line=dict(width=2, color="#FFFFFF")),
        fill="tozeroy",
        fillcolor="rgba(37, 99, 235, 0.10)",
    )
    _style_plotly_chart(chart, height=chart_height, xaxis_title=None, yaxis_title=metric_label)
    st.plotly_chart(chart, width="stretch", key=chart_key)


def _render_executive_tab(
    flags: pd.DataFrame,
    summary: pd.DataFrame,
    components: pd.DataFrame,
    granularity_label: str,
) -> None:
    st.subheader("Bức tranh điều hành")
    st.caption("Tab này dành cho người xem tổng quan: có nhìn ngay xu hướng, dịch vụ chịu ảnh hưởng và nhóm WCC cần ưu tiên.")

    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            _render_main_trend(summary, granularity_label, "Đơn bị flag", "executive_main_trend", chart_height=EXECUTIVE_CARD_HEIGHT)
    with right:
        with st.container(border=True):
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
                color_discrete_sequence=["#3B82F6"],
                text="flagged_orders",
            )
            service_chart.update_traces(textposition="outside")
            _style_plotly_chart(service_chart, height=EXECUTIVE_CARD_HEIGHT, xaxis_title=None, yaxis_title=None)
            st.plotly_chart(service_chart, width="stretch", key="executive_service_chart")

    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            st.markdown("#### Tổng hợp theo kỳ")
            _show_table(
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
                height=EXECUTIVE_CARD_HEIGHT,
            )
    with right:
        with st.container(border=True):
            st.markdown("#### Nhóm WCC nào cần ưu tiên?")
            st.caption("Top nhóm WCC theo điểm ưu tiên")
            if components.empty:
                st.info("Không có dữ liệu nhóm WCC.")
            else:
                component_chart = px.bar(
                    components.head(10).sort_values("max_priority_score", ascending=True),
                    x="max_priority_score",
                    y="component_display_id",
                    orientation="h",
                    title="Top nhóm WCC theo điểm ưu tiên",
                    hover_data=["component_size", "flagged_orders", "top_service", "top_rule"],
                    color_discrete_sequence=["#3B82F6"],
                    text="max_priority_score",
                )
                component_chart.update_traces(texttemplate="%{text:.2f}", textposition="outside")
                _style_plotly_chart(component_chart, height=EXECUTIVE_CARD_HEIGHT, xaxis_title=None, yaxis_title=None)
                st.plotly_chart(component_chart, width="stretch", key="executive_component_chart")


def _render_analyst_tab(
    flags: pd.DataFrame,
    pairs: pd.DataFrame,
    reasons: pd.DataFrame,
    summary: pd.DataFrame,
    granularity_label: str,
) -> None:
    st.subheader("Phân tích chuyên sâu cho analyst")
    st.caption("Tab này dành cho analyst: soi xu hướng, so sánh dịch vụ hoặc rule và xem cặp đáng nghi nhất.")

    metric_label = st.selectbox("Chỉ số phân tích xu hướng", options=list(METRIC_OPTIONS.keys()), index=0)
    left, right = st.columns([1.2, 1])
    with left:
        with st.container(border=True):
            _render_main_trend(summary, granularity_label, metric_label, f"analyst_trend_{metric_label}")

    with right:
        with st.container(border=True):
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
                color_discrete_sequence=["#3B82F6"],
                text="flagged_orders",
            )
            chart.update_traces(textposition="outside")
            _style_plotly_chart(chart, xaxis_title=None, yaxis_title=None)
            st.plotly_chart(chart, width="stretch", key=f"analyst_breakdown_{group_col}")

    left, right = st.columns([1.1, 1])
    with left:
        with st.container(border=True):
            st.markdown("#### Top cặp tài xế - khách hàng đáng nghi")
            pair_summary = build_pair_summary(pairs)
            if pair_summary.empty:
                st.info("Không có dữ liệu cặp đáng nghi trong bộ lọc hiện tại.")
            else:
                _show_table(pair_summary.head(20).rename(columns=PAIR_COLUMN_LABELS))
    with right:
        with st.container(border=True):
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
                _show_table(reason_view)


def _render_component_tab(components: pd.DataFrame, flags: pd.DataFrame) -> None:
    st.subheader("Điều tra nhóm WCC")
    st.caption("Tab này dành cho investigator: xem nhóm liên kết nào lớn, mạnh và đáng điều tra trước.")
    if components.empty:
        st.info("Không có dữ liệu nhóm WCC trong bộ lọc hiện tại.")
        return

    with st.container(border=True):
        overview = components[
            [
                "component_display_id",
                "component_size",
                "flagged_orders",
                "flagged_drivers",
                "flagged_customers",
                "flagged_pairs",
                "max_priority_score",
                "avg_network_support_score",
                "top_service",
                "top_rule",
            ]
        ].rename(
            columns={
                "component_display_id": "ID nhóm WCC",
                "component_size": "Kích thước nhóm",
                "flagged_orders": "Số đơn bị flag",
                "flagged_drivers": "Số tài xế",
                "flagged_customers": "Số khách hàng",
                "flagged_pairs": "Số cặp",
                "max_priority_score": "Điểm ưu tiên cao nhất",
                "avg_network_support_score": "Điểm hỗ trợ mạng",
                "top_service": "Dịch vụ nổi bật",
                "top_rule": "Rule chính",
            }
        )
        _show_table(overview.head(15))

    component_options = components[["component_id", "component_display_id"]].dropna(subset=["component_id"]).copy()
    component_labels = dict(zip(component_options["component_id"].astype(str), component_options["component_display_id"].astype(str)))
    selected_component = st.selectbox(
        "Chọn nhóm WCC để xem chi tiết",
        options=component_options["component_id"].astype(str).tolist(),
        format_func=lambda raw_id: component_labels.get(str(raw_id), str(raw_id)),
    )
    component_flags = flags[flags["component_id"].astype(str) == selected_component].copy()
    component_row = components[components["component_id"].astype(str) == selected_component].iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Kích thước nhóm", f"{int(component_row['component_size']):,}")
    c2.metric("Số đơn bị flag", f"{int(component_row['flagged_orders']):,}")
    c3.metric("Số tài xế", f"{int(component_row['flagged_drivers']):,}")
    c4.metric("Số khách hàng", f"{int(component_row['flagged_customers']):,}")

    st.info(
        f"{component_row.get('component_display_id', component_row['component_id'])} nổi bật ở dịch vụ '{component_row['top_service']}', đang được dẫn bởi rule '{component_row['top_rule']}'."
    )

    detail_columns = [
        column
        for column in [
            "order_id",
            "complete_time_local_tz",
            "driver_id",
            "customer_id",
            "service_name",
            "business_rule_label",
            "priority_score",
            "network_support_score",
            "component_size",
            "risk_tier",
        ]
        if column in component_flags.columns
    ]

    with st.container(border=True):
        _show_table(
            component_flags[detail_columns].sort_values("priority_score", ascending=False).rename(columns=DETAIL_COLUMN_LABELS)
        )
    return

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
            "complete_time_local_tz",
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
    case_sort_columns = ["priority_score"]
    case_sort_ascending = [False]
    if "complete_time_local_tz" in flags.columns:
        case_sort_columns.append("complete_time_local_tz")
        case_sort_ascending.append(False)
    elif "order_date" in flags.columns:
        case_sort_columns.append("order_date")
        case_sort_ascending.append(False)
    detail_frame = flags[detail_columns].sort_values(case_sort_columns, ascending=case_sort_ascending).copy()
    overview_frame = detail_frame.drop_duplicates(subset=["order_id"], keep="first").copy()

    with st.container(border=True):
        _show_table(overview_frame.rename(columns=DETAIL_COLUMN_LABELS))

    selector_mode = st.radio(
        "Xem case theo",
        options=["Đơn", "Tài xế", "Khách hàng"],
        horizontal=True,
        key="case_selector_mode",
    )

    if selector_mode == "Đơn":
        selected_value = st.selectbox(
            "Chọn Đơn bị flag",
            options=overview_frame["order_id"].astype(str).unique().tolist(),
        )
        selected_cases = detail_frame[detail_frame["order_id"].astype(str) == selected_value].copy()
    elif selector_mode == "Tài xế":
        selected_value = st.selectbox(
            "Chọn tài xế",
            options=detail_frame["driver_id"].dropna().astype(str).unique().tolist(),
        )
        selected_cases = detail_frame[detail_frame["driver_id"].astype(str) == selected_value].copy()
    else:
        selected_value = st.selectbox(
            "Chọn khách hàng",
            options=detail_frame["customer_id"].dropna().astype(str).unique().tolist(),
        )
        selected_cases = detail_frame[detail_frame["customer_id"].astype(str) == selected_value].copy()

    if selected_cases.empty:
        st.info("Không có case phù hợp với lựa chọn hiện tại.")
        return

    selected_row = selected_cases.iloc[0]
    unique_rules = selected_cases["business_rule_label"].dropna().astype(str).unique().tolist()
    related_orders = selected_cases["order_id"].astype(str).nunique()
    related_drivers = selected_cases["driver_id"].dropna().astype(str).nunique()
    related_customers = selected_cases["customer_id"].dropna().astype(str).nunique()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Đơn bị flag", f"{related_orders:,}")
    if selector_mode == "Tài xế":
        c2.metric("Tài xế", str(selected_value))
        c3.metric("Khách hàng liên quan", f"{related_customers:,}")
        c4.metric("Rule fraud", f"{len(unique_rules):,}")
    elif selector_mode == "Khách hàng":
        c2.metric("Khách hàng", str(selected_value))
        c3.metric("Tài xế liên quan", f"{related_drivers:,}")
        c4.metric("Rule fraud", f"{len(unique_rules):,}")
    else:
        c2.metric("Tài xế", str(selected_row.get("driver_id", "Không rõ")))
        c3.metric("Khách hàng", str(selected_row.get("customer_id", "Không rõ")))
        c4.metric("Điểm ưu tiên", f"{float(selected_row.get('priority_score', 0)):.2f}")

    left, right = st.columns([1.15, 1])
    with left:
        with st.container(border=True):
            st.markdown("#### Thông tin cơ bản")
            if selector_mode == "Tài xế":
                st.markdown(
                    f"- **Tài xế:** {selected_value}\n"
                    f"- **Số đơn bị flag:** {related_orders:,}\n"
                    f"- **Số khách hàng liên quan:** {related_customers:,}\n"
                    f"- **Mức rủi ro xuất hiện:** {', '.join(sorted(selected_cases['risk_tier'].dropna().astype(str).unique().tolist())) or 'Không rõ'}"
                )
            elif selector_mode == "Khách hàng":
                st.markdown(
                    f"- **Khách hàng:** {selected_value}\n"
                    f"- **Số đơn bị flag:** {related_orders:,}\n"
                    f"- **Số tài xế liên quan:** {related_drivers:,}\n"
                    f"- **Mức rủi ro xuất hiện:** {', '.join(sorted(selected_cases['risk_tier'].dropna().astype(str).unique().tolist())) or 'Không rõ'}"
                )
            else:
                st.markdown(
                    f"- **Đơn:** {selected_row.get('order_id', 'Không rõ')}\n"
                    f"- **Ngày hoàn thành:** {_format_period_value(selected_row.get('complete_time_local_tz'))}\n"
                    f"- **Dịch vụ:** {selected_row.get('service_name', 'Không rõ')}\n"
                    f"- **Mức rủi ro:** {selected_row.get('risk_tier', 'Không rõ')}\n"
                    f"- **Nhóm WCC liên quan:** {selected_row.get('component_id', 'Không rõ')}\n"
                    f"- **Kích thước nhóm:** {selected_row.get('component_size', 'Không rõ')}"
                )
    with right:
        with st.container(border=True):
            st.markdown("#### Rule fraud nghiệp vụ")
            if len(unique_rules) == 1:
                st.markdown(f"**{unique_rules[0]}**")
                st.caption(str(selected_row.get("business_rule_story", "Chưa có diễn giải.")))
            else:
                st.markdown("**Các rule xuất hiện**")
                st.caption(", ".join(unique_rules[:5]))
            st.markdown(
                f"- **Vì sao bị flag:** {selected_row.get('flag_reason_vi', 'Chưa có diễn giải')}\n"
                f"- **Tín hiệu hỗ trợ:** {selected_row.get('supporting_signal_vi', 'Chưa có diễn giải')}\n"
                f"- **Mã lý do flag:** {selected_row.get('reason_code', 'Không rõ')}"
            )

    if selector_mode == "Tài xế":
        related_customers_frame = (
            selected_cases[
                [column for column in ["customer_id", "order_id", "complete_time_local_tz", "business_rule_label", "priority_score"] if column in selected_cases.columns]
            ]
            .sort_values(["priority_score", "complete_time_local_tz"], ascending=[False, False])
            .rename(
                columns={
                    "customer_id": "Khách hàng liên quan",
                    "order_id": "Đơn bị flag",
                    "complete_time_local_tz": "Ngày hoàn thành",
                    "business_rule_label": "Rule fraud nghiệp vụ",
                    "priority_score": "Điểm ưu tiên",
                }
            )
        )
        with st.container(border=True):
            st.markdown("#### Các Đơn bị gắn flag theo tài xế này")
            _show_table(selected_cases.rename(columns=DETAIL_COLUMN_LABELS))
        with st.container(border=True):
            st.markdown("#### Các khách hàng liên quan đến tài xế này")
            _show_table(related_customers_frame)
    elif selector_mode == "Khách hàng":
        related_drivers_frame = (
            selected_cases[
                [column for column in ["driver_id", "order_id", "complete_time_local_tz", "business_rule_label", "priority_score"] if column in selected_cases.columns]
            ]
            .sort_values(["priority_score", "complete_time_local_tz"], ascending=[False, False])
            .rename(
                columns={
                    "driver_id": "Tài xế liên quan",
                    "order_id": "Đơn bị flag",
                    "complete_time_local_tz": "Ngày hoàn thành",
                    "business_rule_label": "Rule fraud nghiệp vụ",
                    "priority_score": "Điểm ưu tiên",
                }
            )
        )
        with st.container(border=True):
            st.markdown("#### Các Đơn bị gắn flag theo khách hàng này")
            _show_table(selected_cases.rename(columns=DETAIL_COLUMN_LABELS))
        with st.container(border=True):
            st.markdown("#### Các tài xế liên quan đến khách hàng này")
            _show_table(related_drivers_frame)
    else:
        with st.container(border=True):
            st.markdown("#### Các case liên quan")
            _show_table(selected_cases.rename(columns=DETAIL_COLUMN_LABELS))
    return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Đơn bị flag", f"{selected_cases['order_id'].astype(str).nunique():,}")
    c2.metric("Tài xế", str(selected_row.get("driver_id", "Không rõ")))
    c3.metric("Khách hàng", str(selected_row.get("customer_id", "Không rõ")))
    c4.metric("Điểm ưu tiên", f"{float(selected_row.get('priority_score', 0)):.2f}")

    left, right = st.columns([1.15, 1])
    with left:
        with st.container(border=True):
            st.markdown("#### Thông tin cơ bản")
            st.markdown(
                f"- **Đơn:** {selected_row.get('order_id', 'Không rõ')}\n"
                # f"- **Ngày Đơn:** {_format_period_value(selected_row.get('order_date'))}\n"
                f"- **Dịch vụ:** {selected_row.get('service_name', 'Không rõ')}\n"
                f"- **Mức rủi ro:** {selected_row.get('risk_tier', 'Không rõ')}\n"
                f"- **Nhóm WCC liên quan:** {selected_row.get('component_id', 'Không rõ')}\n"
                f"- **Kích thước nhóm:** {selected_row.get('component_size', 'Không rõ')}"
            )
    with right:
        with st.container(border=True):
            st.markdown("#### Rule fraud nghiệp vụ")
            st.markdown(f"**{selected_row.get('business_rule_label', 'Không rõ')}**")
            st.caption(str(selected_row.get("business_rule_story", "Chưa có diễn giải.")))
            st.markdown(
                f"- **Vì sao bị flag:** {selected_row.get('flag_reason_vi', 'Chưa có diễn giải')}\n"
                f"- **Tín hiệu hỗ trợ:** {selected_row.get('supporting_signal_vi', 'Chưa có diễn giải')}\n"
                f"- **Mã lý do flag:** {selected_row.get('reason_code', 'Không rõ')}"
            )

    with st.container(border=True):
        st.markdown("#### Các case liên quan")
        _show_table(selected_cases.rename(columns=DETAIL_COLUMN_LABELS))
    return

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
    _inject_dashboard_theme()

    reports = load_reports(str(REPORT_DIR))
    flags = _normalize_flags(reports["flags"])
    pairs = _normalize_pairs(reports["pairs"])
    reasons = _normalize_reasons(reports["reasons"])

    if flags.empty:
        st.warning("Không tìm thấy dữ liệu `flagged_orders.parquet` để dựng dashboard.")
        return

    filters = _render_header_and_filters(flags)
    filtered_flags, filtered_pairs, filtered_reasons = _apply_filters(flags, pairs, reasons, filters)
    if filtered_flags.empty:
        st.warning("Không có dữ liệu trong bộ lọc hiện tại.")
        return

    granularity_label = st.session_state.get("granularity_radio", "Ngày")
    period_col = GRANULARITY_CONFIG[granularity_label]

    metrics = build_overview_metrics(filtered_flags)
    period_summary = build_period_summary(filtered_flags, period_col)
    rule_overview = build_rule_overview(filtered_flags)
    component_summary = build_component_summary(filtered_flags)
    insights = build_insight_summary(period_summary, filtered_flags, rule_overview, component_summary)

    _render_metric_cards(metrics)
    _render_insight_cards(insights)
    _render_rule_story_overview(rule_overview)

    st.caption(
        "Lưu ý: nguồn hiện tại là tập đơn đã bị flag, nên 'Tổng đơn trong tập flagged' không phải tổng số đơn của toàn hệ thống."
    )

    executive_tab, analyst_tab, component_tab, case_tab = st.tabs(
        ["1. Điều hành", "2. Phân tích chuyên sâu", "3. Điều tra nhóm WCC", "4. Điều tra case"]
    )

    with executive_tab:
        _render_executive_tab(filtered_flags, period_summary, component_summary, granularity_label)

    with analyst_tab:
        _render_analyst_tab(filtered_flags, filtered_pairs, filtered_reasons, period_summary, granularity_label)

    with component_tab:
        _render_component_tab(component_summary, filtered_flags)

    with case_tab:
        _render_case_tab(filtered_flags)


if __name__ == "__main__":
    render_dashboard()
