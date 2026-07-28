"""Plain-language daily operations dashboard for the KB-C fraud rule."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src.config.settings import settings
from src.dashboard.app import (
    REPORT_DIR,
    add_rule_display,
    build_entity_summary,
    build_kbc_daily_summary,
    build_kbc_metric_guide,
    build_kbc_reason_pair_summary,
    build_neo4j_query_pack,
    build_window_metrics,
    read_reports,
)


REASON_NAMES = {
    "KB-C_EXTREME_VOLUME": "Di cung nhau qua nhieu",
    "KB-C_HIGH_GHOST_RATE": "Nhieu chuyen khong di chuyen",
    "KB-C_SUPERFAST_GAP": "Hai chuyen qua sat nhau",
    "KB-C_TIGHT_PAIR_SHARE": "Phu thuoc manh vao mot cap",
    "KB-C_ROUTE_LOOP": "Lap lai cung tuyen duong",
}

RISK_TIER_ORDER = ["HIGH", "MEDIUM", "WATCHLIST"]
RISK_TIER_LABELS = {
    "HIGH": "High",
    "MEDIUM": "Medium",
    "WATCHLIST": "Watchlist",
}


def metric_guide() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Chi so": "Cap bi canh bao",
                "Y nghia": "So cap tai xe - khach hang bi giu lai sau khi ap nguong va bo loc hien tai.",
            },
            {
                "Chi so": "Risk tier",
                "Y nghia": "Muc uu tien review hien tai cua pair: HIGH, MEDIUM hoac WATCHLIST.",
            },
            {
                "Chi so": "Rule score base",
                "Y nghia": "Diem rule nen den tu hanh vi truc tiep cua pair nhu tan suat chuyen, ghost rate va min gap.",
            },
            {
                "Chi so": "Graph risk score",
                "Y nghia": "Diem bo sung tu suspicious pair graph: pair nay dính voi bao nhieu pair dang ngo khac va co bao nhieu tin hieu chia se.",
            },
            {
                "Chi so": "Final risk score",
                "Y nghia": "Diem xep hang cuoi cung de sap danh sach review. Trong output hien tai `rule_score` dang bam theo diem nay.",
            },
            {
                "Chi so": "Component size",
                "Y nghia": "So pair nam trong cung connected component nghia la cung mot cum lien ket nghi ngo.",
            },
            {
                "Chi so": "Linked pair count",
                "Y nghia": "So pair dang ngo khac noi truc tiep voi pair hien tai qua payment, promo, pickup, dropoff hoac route.",
            },
        ]
    )


def _apply_style() -> None:
    st.markdown(
        """
        <style>
        .stApp {background: linear-gradient(180deg, #f7f4ed 0%, #ffffff 360px);}
        [data-testid="stMetric"] {
            background: #ffffff; border: 1px solid #e7e1d6; border-radius: 14px;
            padding: 16px 18px; box-shadow: 0 6px 24px rgba(45, 38, 25, .05);
        }
        [data-testid="stMetricLabel"] {color: #625b4d;}
        [data-testid="stMetricValue"] {color: #173f35;}
        .block-container {padding-top: 2rem; padding-bottom: 4rem;}
        div[data-testid="stTabs"] button {font-size: 1rem; font-weight: 650;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _latest_date(flags: pd.DataFrame) -> object | None:
    if flags.empty or "order_date" not in flags.columns:
        return None
    parsed = pd.to_datetime(flags["order_date"], errors="coerce").dropna()
    return parsed.max().date() if not parsed.empty else None


def _pair_sort_columns(pairs: pd.DataFrame) -> list[str]:
    candidates = ["final_risk_score", "rule_score", "graph_risk_score", "n_trips"]
    return [column for column in candidates if column in pairs.columns]


def _sorted_pairs(pairs: pd.DataFrame) -> pd.DataFrame:
    sort_cols = _pair_sort_columns(pairs)
    if not sort_cols:
        return pairs.copy()
    return pairs.sort_values(sort_cols, ascending=[False] * len(sort_cols)).copy()


def _filter_data(
    pairs: pd.DataFrame,
    reasons: pd.DataFrame,
    flags: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    st.sidebar.header("Bo loc danh sach")
    st.sidebar.caption("Mac dinh dang uu tien nhom can review som nhat.")
    selected_tiers = st.sidebar.multiselect(
        "Risk tier",
        options=RISK_TIER_ORDER,
        default=RISK_TIER_ORDER,
        format_func=lambda value: RISK_TIER_LABELS.get(value, value),
    )
    min_trips = int(pairs["n_trips"].min())
    max_trips = int(pairs["n_trips"].max())
    trip_cutoff = st.sidebar.slider(
        "It nhat bao nhieu chuyen",
        min_trips,
        max_trips,
        min(12, max_trips),
        help="So chuyen cua cung mot tai xe va khach hang trong ky du lieu.",
    )
    with st.sidebar.expander("Bo loc nang cao"):
        max_gap = min(10.0, float(pairs["min_gap_min"].max()))
        gap_cutoff = st.slider("Khoang cach toi da (phut)", 0.0, max(10.0, max_gap), 5.0, 0.5)
        ghost_cutoff = st.slider("Ty le khong di chuyen toi thieu", 0.0, 1.0, 0.0, 0.05)
        max_final_score = float(pairs["final_risk_score"].max()) if "final_risk_score" in pairs.columns else 100.0
        final_score_cutoff = st.slider("Diem cuoi cung toi thieu", 0.0, max(100.0, max_final_score), 0.0, 1.0)

    filtered = pairs[
        (pairs["n_trips"] >= trip_cutoff)
        & (pairs["min_gap_min"] <= gap_cutoff)
        & (pairs["ghost_rate"] >= ghost_cutoff)
    ].copy()
    if "risk_tier" in filtered.columns and selected_tiers:
        filtered = filtered[filtered["risk_tier"].isin(selected_tiers)]
    if "final_risk_score" in filtered.columns:
        filtered = filtered[filtered["final_risk_score"] >= final_score_cutoff]

    keys = filtered[["driver_id", "customer_id"]]
    filtered_reasons = (
        reasons.merge(keys, on=["driver_id", "customer_id"], how="inner")
        if not reasons.empty
        else pd.DataFrame()
    )
    filtered_flags = (
        flags.merge(keys, on=["driver_id", "customer_id"], how="inner")
        if not flags.empty
        else pd.DataFrame()
    )
    return filtered, filtered_reasons, filtered_flags


def _render_overview(
    daily: pd.DataFrame,
    pairs: pd.DataFrame,
    reasons: pd.DataFrame,
    flags: pd.DataFrame,
) -> None:
    st.subheader("Tinh hinh canh bao")
    st.caption("Phan nay tra loi nhanh: hien co bao nhieu pair can review va dang nghiem trong den dau.")
    windows = build_window_metrics(flags)
    if not windows.empty:
        labels = {"1D": "Ngay gan nhat", "7D": "7 ngay", "30D": "30 ngay"}
        columns = st.columns(3)
        for index, row in windows.reset_index(drop=True).iterrows():
            columns[index].metric(
                labels[row["window_label"]],
                f"{int(row['flagged_orders']):,} don",
                help=(
                    f"Tu {row['start_date']} den {row['end_date']} | "
                    f"HIGH {int(row.get('high_risk_orders', 0)):,} | "
                    f"MEDIUM {int(row.get('medium_risk_orders', 0)):,} | "
                    f"WATCHLIST {int(row.get('watchlist_orders', 0)):,}"
                ),
            )

    customer_summary = build_entity_summary(flags, "customer_id")
    driver_summary = build_entity_summary(flags, "driver_id")
    columns = st.columns(6)
    columns[0].metric("Cap can review", f"{len(pairs):,}")
    columns[1].metric("Risk HIGH", f"{int(pairs['risk_tier'].eq('HIGH').sum()):,}" if "risk_tier" in pairs.columns else "0")
    columns[2].metric("Risk MEDIUM", f"{int(pairs['risk_tier'].eq('MEDIUM').sum()):,}" if "risk_tier" in pairs.columns else "0")
    columns[3].metric("Risk WATCHLIST", f"{int(pairs['risk_tier'].eq('WATCHLIST').sum()):,}" if "risk_tier" in pairs.columns else "0")
    columns[4].metric("Diem cuoi TB", f"{float(pairs['final_risk_score'].mean()):.1f}" if "final_risk_score" in pairs.columns else "n/a")
    columns[5].metric("Component lon nhat", f"{int(pairs['component_size'].max()):,}" if "component_size" in pairs.columns else "n/a")

    st.info(
        "Dashboard hien dang xep uu tien pair theo `final_risk_score`. "
        "Score nay ket hop score rule nen va score graph hien tai, nghia la vua nhin hanh vi cua pair, "
        "vua nhin pair do dang dính voi bao nhieu pair dang ngo khac."
    )

    left, right = st.columns([3, 2])
    with left:
        trend = px.bar(
            daily,
            x="order_date",
            y="flagged_orders",
            text="flagged_orders",
            labels={"order_date": "Ngay", "flagged_orders": "So don bi canh bao"},
            title="So don bi canh bao theo ngay",
            color_discrete_sequence=["#d97745"],
        )
        trend.update_traces(textposition="outside")
        trend.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(trend, width="stretch")
    with right:
        summary = build_kbc_reason_pair_summary(reasons)
        if not summary.empty:
            summary["Ly do"] = summary["reason_code"].map(REASON_NAMES).fillna(summary["reason_code"])
            reason_chart = px.bar(
                summary,
                x="flagged_pairs",
                y="Ly do",
                orientation="h",
                labels={"flagged_pairs": "So cap"},
                title="Canh bao den tu dau?",
                color_discrete_sequence=["#2d6a5b"],
            )
            reason_chart.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(reason_chart, width="stretch")

    graph_left, graph_right = st.columns(2)
    with graph_left:
        if "risk_tier" in pairs.columns:
            tier_summary = (
                pairs.groupby("risk_tier", dropna=False)
                .agg(pair_count=("driver_id", "size"), avg_final_risk_score=("final_risk_score", "mean"))
                .reset_index()
            )
            tier_summary["risk_tier"] = pd.Categorical(
                tier_summary["risk_tier"], categories=RISK_TIER_ORDER, ordered=True
            )
            tier_summary = tier_summary.sort_values("risk_tier")
            tier_chart = px.bar(
                tier_summary,
                x="risk_tier",
                y="pair_count",
                text="pair_count",
                color="risk_tier",
                title="So pair theo risk tier",
                color_discrete_map={"HIGH": "#c2412d", "MEDIUM": "#d97745", "WATCHLIST": "#d4a72c"},
            )
            tier_chart.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(tier_chart, width="stretch")
    with graph_right:
        if {"component_size", "linked_pair_count", "final_risk_score"} <= set(pairs.columns):
            graph_chart = px.scatter(
                _sorted_pairs(pairs).head(150),
                x="linked_pair_count",
                y="component_size",
                size="final_risk_score",
                color="risk_tier" if "risk_tier" in pairs.columns else None,
                hover_data=["driver_id", "customer_id", "supporting_signal_count", "graph_risk_score"],
                title="Pair dang dinh voi bao nhieu pair khac?",
                color_discrete_map={"HIGH": "#c2412d", "MEDIUM": "#d97745", "WATCHLIST": "#d4a72c"},
            )
            graph_chart.update_layout(plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(graph_chart, width="stretch")

    st.subheader("Ai xuat hien nhieu nhat?")
    left, right = st.columns(2)
    for column, summary, entity, color in (
        (left, customer_summary, "Khach hang", "#d4a72c"),
        (right, driver_summary, "Tai xe", "#3c7c8a"),
    ):
        with column:
            id_column = "customer_id" if entity == "Khach hang" else "driver_id"
            if not summary.empty:
                chart = px.bar(
                    summary.head(10),
                    x="flagged_orders",
                    y=id_column,
                    orientation="h",
                    labels={"flagged_orders": "So don", id_column: entity},
                    title=f"10 {entity.lower()} co nhieu don bi canh bao",
                    color_discrete_sequence=[color],
                    hover_data=[
                        column_name
                        for column_name in (
                            "high_conf_orders",
                            "avg_graph_risk_score",
                            "max_final_risk_score",
                            "max_component_size",
                        )
                        if column_name in summary.columns
                    ],
                )
                chart.update_layout(yaxis={"categoryorder": "total ascending"}, showlegend=False)
                st.plotly_chart(chart, width="stretch")


def _render_review(pairs: pd.DataFrame) -> None:
    st.subheader("Danh sach uu tien kiem tra")
    st.caption(
        "Danh sach da xep theo score cuoi cung va ngu canh graph. Moi dong la mot pair driver - customer."
    )
    table = _sorted_pairs(pairs)
    if "risk_tier" in table.columns:
        table["Muc do"] = table["risk_tier"].map(RISK_TIER_LABELS).fillna(table["risk_tier"])
    elif "high_confidence" in table.columns:
        table["Muc do"] = table["high_confidence"].map({True: "High confidence", False: "Theo doi"})
    else:
        table["Muc do"] = "Theo doi"
    table["Ty le khong di chuyen"] = table["ghost_rate"].map(lambda value: f"{value:.1%}")
    table["Khoang cach ngan nhat"] = table["min_gap_min"].map(lambda value: f"{value:.1f} phut")
    table["GMV trung binh"] = table["avg_gmv"].map(lambda value: f"{value:,.0f} d")
    columns = {
        "Muc do": "Muc do",
        "driver_id": "Ma tai xe",
        "customer_id": "Ma khach hang",
        "n_trips": "So chuyen",
        "n_ghost": "Chuyen khong di chuyen",
        "Ty le khong di chuyen": "Ty le khong di chuyen",
        "Khoang cach ngan nhat": "Khoang cach ngan nhat",
        "rule_score_base": "Rule base",
        "graph_risk_score": "Graph score",
        "final_risk_score": "Final score",
        "linked_pair_count": "Linked pairs",
        "supporting_signal_count": "Shared signals",
        "component_size": "Component size",
        "GMV trung binh": "GMV trung binh",
    }
    visible_columns = [column for column in columns if column in table.columns]
    st.dataframe(
        table[visible_columns].rename(columns=columns).head(200),
        width="stretch",
        hide_index=True,
        column_config={"Final score": st.column_config.ProgressColumn(min_value=0.0, max_value=100.0)},
    )

    st.subheader("Ban do muc do bat thuong")
    st.caption(
        "Cang sang trai: hai chuyen cang sat nhau. Cang len tren: cang nhieu chuyen khong di chuyen. "
        "Bong bong cang lon: diem cuoi cung cang cao."
    )
    chart_data = table.head(150)
    color_column = "risk_tier" if "risk_tier" in chart_data.columns else "Muc do"
    chart = px.scatter(
        chart_data,
        x="min_gap_min",
        y="ghost_rate",
        size="final_risk_score" if "final_risk_score" in chart_data.columns else "n_trips",
        color=color_column,
        color_discrete_map={"HIGH": "#c2412d", "MEDIUM": "#d97745", "WATCHLIST": "#d4a72c"},
        labels={
            "min_gap_min": "Khoang cach ngan nhat giua hai chuyen (phut)",
            "ghost_rate": "Ty le chuyen khong di chuyen",
            "final_risk_score": "Final score",
        },
        hover_data={
            "driver_id": True,
            "customer_id": True,
            "rule_score_base": ":.2f" if "rule_score_base" in chart_data.columns else False,
            "graph_risk_score": ":.2f" if "graph_risk_score" in chart_data.columns else False,
            "linked_pair_count": True if "linked_pair_count" in chart_data.columns else False,
        },
    )
    chart.add_vline(x=5, line_dash="dash", line_color="#8b8170")
    chart.add_hline(y=0.3, line_dash="dash", line_color="#8b8170")
    chart.update_layout(plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(chart, width="stretch")


def _render_detail(pairs: pd.DataFrame, reasons: pd.DataFrame, flags: pd.DataFrame) -> None:
    st.subheader("Tra cuu mot cap tai xe - khach hang")
    st.caption("Chon mot cap de xem score, ly do canh bao, ngu canh graph va danh sach don lien quan.")
    options = _sorted_pairs(pairs).assign(
        label=lambda frame: frame.apply(
            lambda row: (
                f"Tai xe {row['driver_id']} | Khach {row['customer_id']} | "
                f"{int(row['n_trips'])} chuyen | final {float(row.get('final_risk_score', row.get('rule_score', 0.0))):.1f}"
            ),
            axis=1,
        )
    )
    label = st.selectbox("Cap can xem", options["label"].head(200), label_visibility="collapsed")
    selected = options.loc[options["label"] == label].iloc[0]

    columns = st.columns(6)
    columns[0].metric("Tong so chuyen", f"{int(selected['n_trips']):,}")
    columns[1].metric("Chuyen khong di chuyen", f"{int(selected['n_ghost']):,}")
    columns[2].metric("Ty le khong di chuyen", f"{float(selected['ghost_rate']):.1%}")
    columns[3].metric("Min gap", f"{float(selected['min_gap_min']):.1f} phut")
    columns[4].metric("Rule base", f"{float(selected.get('rule_score_base', selected.get('rule_score', 0.0))):.1f}")
    columns[5].metric("Final score", f"{float(selected.get('final_risk_score', selected.get('rule_score', 0.0))):.1f}")

    graph_columns = st.columns(4)
    graph_columns[0].metric("Risk tier", str(selected.get("risk_tier", "n/a")))
    graph_columns[1].metric("Graph score", f"{float(selected.get('graph_risk_score', 0.0)):.1f}")
    graph_columns[2].metric("Linked pairs", f"{int(selected.get('linked_pair_count', 0)):,}")
    graph_columns[3].metric("Component size", f"{int(selected.get('component_size', 0)):,}")

    supporting_columns = st.columns(4)
    supporting_columns[0].metric("Shared signals", f"{int(selected.get('supporting_signal_count', 0)):,}")
    supporting_columns[1].metric("Shared payment", f"{int(selected.get('shared_payment_count', 0)):,}")
    supporting_columns[2].metric("Shared promo", f"{int(selected.get('shared_promo_count', 0)):,}")
    supporting_columns[3].metric("Shared route", f"{int(selected.get('shared_route_count', 0)):,}")

    pair_reasons = reasons[
        (reasons["driver_id"] == selected["driver_id"])
        & (reasons["customer_id"] == selected["customer_id"])
    ]
    if not pair_reasons.empty:
        readable_reasons = pair_reasons["reason_code"].map(REASON_NAMES).fillna(pair_reasons["reason_code"])
        st.warning("Cap nay duoc canh bao vi: " + " | ".join(readable_reasons.unique()))

    st.markdown("**Graph context hien tai**")
    st.markdown(
        "Pair nay khong duoc cham theo kieu graph tu tach cong dong toi uu. "
        "Phan graph dang chay that la pair nay co dính voi bao nhieu pair dang ngo khac va chia se bao nhieu tin hieu."
    )

    orders = flags[
        (flags["driver_id"] == selected["driver_id"])
        & (flags["customer_id"] == selected["customer_id"])
    ].copy()
    if orders.empty:
        st.info("Khong tim thay danh sach don cua cap nay trong du lieu hien tai.")
        return

    orders = orders.sort_values("order_time_local_tz", ascending=False)
    order_columns = {
        "order_id": "Ma don",
        "order_time_local_tz": "Thoi gian dat",
        "complete_time_local_tz": "Thoi gian hoan thanh",
        "service_name": "Dich vu",
        "avg_kmh": "Toc do TB (km/h)",
        "gmv": "Gia tri don",
        "reason_code": "Ly do",
        "pickup_address": "Diem don",
        "last_dropoff_address": "Diem tra",
    }
    available = [column for column in order_columns if column in orders.columns]
    st.subheader("Cac don lien quan")
    st.dataframe(
        orders[available].rename(columns=order_columns).head(200),
        width="stretch",
        hide_index=True,
    )

    with st.expander("Xem tren do thi Neo4j (danh cho nguoi phan tich)"):
        st.markdown(f"Mo Neo4j tai `{settings.neo4j_ride_browser_url}`, sau do chay cau truy van phu hop.")
        query_names = {
            "Customer-driver repetition": "Toan bo don cua cap nay",
            "Selected order details": "Chi tiet mot don",
            "Customer timeline and linked drivers": "Khach hang da di voi nhung tai xe nao",
            "Driver timeline and linked customers": "Tai xe da cho nhung khach hang nao",
            "Pair route and time reuse": "Tuyen duong va thoi gian bi lap",
        }
        queries = build_neo4j_query_pack("REPEATED_CUSTOMER_DRIVER", orders.iloc[0])
        for key, title in query_names.items():
            if key in queries:
                st.markdown(f"**{title}**")
                st.code(queries[key], language="cypher")


def render_dashboard(report_dir: Path = REPORT_DIR) -> None:
    st.set_page_config(page_title="Theo doi cuoc xe bat thuong", page_icon="🚕", layout="wide")
    _apply_style()
    selected_report_dir = st.sidebar.text_input("Thu muc bao cao", str(report_dir))
    reports = read_reports(selected_report_dir)
    daily = build_kbc_daily_summary(add_rule_display(reports["daily"]))
    flags = add_rule_display(reports["flags"])
    pairs = reports["kbc_pairs"]
    reasons = reports["kbc_reasons"]
    known_cases = reports["kbc_known"]

    st.title("Theo doi cuoc xe bat thuong")
    st.markdown(
        "Phat hien cac cap **tai xe - khach hang di cung nhau qua nhieu**, tao cuoc qua nhanh "
        "hoac co dau hieu cuoc khong thuc su di chuyen."
    )
    if daily.empty or pairs.empty:
        st.warning("Chua co du lieu bao cao. Hay chay tac vu cap nhat du lieu hang ngay truoc.")
        st.code("python -m scripts.build_task3_daily_outputs", language="powershell")
        return

    latest = _latest_date(flags)
    latest_text = latest.strftime("%d/%m/%Y") if latest else "chua xac dinh"
    st.caption(f"Du lieu moi nhat: **{latest_text}** | KB-C: cap tai xe - khach hang sieu toc")

    filtered_pairs, filtered_reasons, filtered_flags = _filter_data(pairs, reasons, flags)
    if filtered_pairs.empty:
        st.info("Khong co truong hop phu hop voi bo loc. Hay noi bo loc o thanh ben trai.")
        return

    overview, review, detail, guide = st.tabs(
        ["Tong quan", "Danh sach can kiem tra", "Tra cuu chi tiet", "Huong dan"]
    )
    with overview:
        _render_overview(daily, filtered_pairs, filtered_reasons, filtered_flags)
    with review:
        _render_review(filtered_pairs)
    with detail:
        _render_detail(filtered_pairs, filtered_reasons, filtered_flags)
    with guide:
        st.subheader("Dashboard dang phat hien dieu gi?")
        st.markdown(
            "He thong hien tai cham pair driver - customer theo hai lop. "
            "Lop thu nhat la hanh vi truc tiep cua pair nhu `n_trips`, `ghost_rate`, `min_gap_min`. "
            "Lop thu hai la suspicious pair graph: pair do dang noi voi bao nhieu pair dang ngo khac va co bao nhieu tin hieu chia se."
        )
        st.markdown(
            "Noi cach khac, phan graph dang chay that hien tai la: "
            "**pair nao dang ngo, pair do co dính voi bao nhieu pair khac**. "
            "Chua phai bai toan graph tu tach toan bo cong dong gian lan toi uu."
        )
        st.dataframe(metric_guide(), width="stretch", hide_index=True)
        st.subheader("Metric guide ky thuat")
        st.dataframe(build_kbc_metric_guide(), width="stretch", hide_index=True)
        st.info(
            "Nguong nghiem trong hien tai van giu nguyen: ty le chuyen khong di chuyen tren 30%, "
            "hoac khoang cach ngan nhat giua hai chuyen duoi 5 phut."
        )
        if not known_cases.empty:
            with st.expander("Ket qua kiem tra voi cac truong hop da biet"):
                st.dataframe(known_cases, width="stretch", hide_index=True)
