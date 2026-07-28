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
    build_kbc_reason_pair_summary,
    build_neo4j_query_pack,
    build_window_metrics,
    read_reports,
)


REASON_NAMES = {
    "KB-C_EXTREME_VOLUME": "Đi cùng nhau quá nhiều",
    "KB-C_HIGH_GHOST_RATE": "Nhiều chuyến không di chuyển",
    "KB-C_SUPERFAST_GAP": "Hai chuyến quá sát nhau",
    "KB-C_TIGHT_PAIR_SHARE": "Phụ thuộc mạnh vào một cặp",
    "KB-C_ROUTE_LOOP": "Lặp lại cùng tuyến đường",
}


def metric_guide() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Chỉ số": "Cặp bị cảnh báo",
                "Ý nghĩa": "Số cặp tài xế - khách hàng có tần suất chuyến bất thường và cần được kiểm tra.",
            },
            {
                "Chỉ số": "Cảnh báo nghiêm trọng",
                "Ý nghĩa": "Cặp có trên 30% chuyến không di chuyển hoặc có hai chuyến cách nhau dưới 5 phút.",
            },
            {
                "Chỉ số": "Đơn cần kiểm tra",
                "Ý nghĩa": "Tổng số đơn thuộc các cặp đang bị cảnh báo.",
            },
            {
                "Chỉ số": "Khoảng cách ngắn nhất",
                "Ý nghĩa": "Số phút ngắn nhất giữa hai đơn liên tiếp của cùng một cặp. Càng nhỏ càng đáng ngờ.",
            },
            {
                "Chỉ số": "Tỷ lệ không di chuyển",
                "Ý nghĩa": "Tỷ lệ đơn có tốc độ trung bình bằng 0. Tỷ lệ cao có thể là dấu hiệu cuốc giả.",
            },
            {
                "Chỉ số": "Điểm ưu tiên",
                "Ý nghĩa": "Điểm tổng hợp để xếp thứ tự kiểm tra. Điểm càng cao thì nên kiểm tra càng sớm.",
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


def _filter_data(
    pairs: pd.DataFrame,
    reasons: pd.DataFrame,
    flags: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    st.sidebar.header("Bộ lọc danh sách")
    st.sidebar.caption("Có thể giữ nguyên để xem các trường hợp cần ưu tiên nhất.")
    serious_only = st.sidebar.checkbox(
        "Chỉ xem cảnh báo nghiêm trọng",
        value=True,
        help="Trên 30% chuyến không di chuyển hoặc hai chuyến cách nhau dưới 5 phút.",
    )
    min_trips = int(pairs["n_trips"].min())
    max_trips = int(pairs["n_trips"].max())
    trip_cutoff = st.sidebar.slider(
        "Ít nhất bao nhiêu chuyến",
        min_trips,
        max_trips,
        min(12, max_trips),
        help="Số chuyến của cùng một tài xế và khách hàng trong kỳ dữ liệu.",
    )
    with st.sidebar.expander("Bộ lọc nâng cao"):
        max_gap = min(10.0, float(pairs["min_gap_min"].max()))
        gap_cutoff = st.slider("Khoảng cách tối đa (phút)", 0.0, max(10.0, max_gap), 5.0, 0.5)
        ghost_cutoff = st.slider("Tỷ lệ không di chuyển tối thiểu", 0.0, 1.0, 0.0, 0.05)

    filtered = pairs[
        (pairs["n_trips"] >= trip_cutoff)
        & (pairs["min_gap_min"] <= gap_cutoff)
        & (pairs["ghost_rate"] >= ghost_cutoff)
    ].copy()
    if serious_only:
        filtered = filtered[filtered["high_confidence"].fillna(False)]

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
    st.subheader("Tình hình cảnh báo")
    st.caption("Ba con số đầu tiên cần xem khi bắt đầu ngày làm việc.")
    windows = build_window_metrics(flags)
    if not windows.empty:
        labels = {"1D": "Trong ngày gần nhất", "7D": "Trong 7 ngày", "30D": "Trong 30 ngày"}
        columns = st.columns(3)
        for index, row in windows.reset_index(drop=True).iterrows():
            columns[index].metric(
                labels[row["window_label"]],
                f"{int(row['flagged_orders']):,} đơn",
                help=f"Dữ liệu từ {row['start_date']} đến {row['end_date']}.",
            )

    customer_summary = build_entity_summary(flags, "customer_id")
    driver_summary = build_entity_summary(flags, "driver_id")
    columns = st.columns(4)
    columns[0].metric("Cặp cần kiểm tra", f"{len(pairs):,}")
    columns[1].metric("Cảnh báo nghiêm trọng", f"{int(pairs['high_confidence'].sum()):,}")
    columns[2].metric("Khách hàng liên quan", f"{flags['customer_id'].nunique():,}")
    columns[3].metric("Tài xế liên quan", f"{flags['driver_id'].nunique():,}")

    st.info(
        "**Việc nên làm tiếp theo:** kiểm tra các cặp nghiêm trọng trước, sau đó xem lịch sử đơn "
        "và địa điểm trong tab “Tra cứu chi tiết”. Cảnh báo là tín hiệu cần rà soát, không phải kết luận gian lận."
    )

    left, right = st.columns([3, 2])
    with left:
        trend = px.bar(
            daily,
            x="order_date",
            y="flagged_orders",
            text="flagged_orders",
            labels={"order_date": "Ngày", "flagged_orders": "Số đơn bị cảnh báo"},
            title="Số đơn bị cảnh báo theo ngày",
            color_discrete_sequence=["#d97745"],
        )
        trend.update_traces(textposition="outside")
        trend.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(trend, width="stretch")
    with right:
        summary = build_kbc_reason_pair_summary(reasons)
        if not summary.empty:
            summary["Lý do"] = summary["reason_code"].map(REASON_NAMES).fillna(summary["reason_code"])
            reason_chart = px.bar(
                summary,
                x="flagged_pairs",
                y="Lý do",
                orientation="h",
                labels={"flagged_pairs": "Số cặp"},
                title="Cảnh báo đến từ đâu?",
                color_discrete_sequence=["#2d6a5b"],
            )
            reason_chart.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(reason_chart, width="stretch")

    st.subheader("Ai xuất hiện nhiều nhất?")
    left, right = st.columns(2)
    for column, summary, entity, color in (
        (left, customer_summary, "Khách hàng", "#d4a72c"),
        (right, driver_summary, "Tài xế", "#3c7c8a"),
    ):
        with column:
            id_column = "customer_id" if entity == "Khách hàng" else "driver_id"
            if not summary.empty:
                chart = px.bar(
                    summary.head(10),
                    x="flagged_orders",
                    y=id_column,
                    orientation="h",
                    labels={"flagged_orders": "Số đơn", id_column: entity},
                    title=f"10 {entity.lower()} có nhiều đơn bị cảnh báo",
                    color_discrete_sequence=[color],
                )
                chart.update_layout(yaxis={"categoryorder": "total ascending"}, showlegend=False)
                st.plotly_chart(chart, width="stretch")


def _render_review(pairs: pd.DataFrame) -> None:
    st.subheader("Danh sách ưu tiên kiểm tra")
    st.caption(
        "Danh sách đã xếp theo mức độ nghiêm trọng, điểm ưu tiên và số chuyến. "
        "Mỗi dòng là một cặp tài xế - khách hàng."
    )
    table = pairs.sort_values(
        ["high_confidence", "rule_score", "n_trips"], ascending=[False, False, False]
    ).copy()
    table["Mức độ"] = table["high_confidence"].map({True: "Nghiêm trọng", False: "Cần theo dõi"})
    table["Tỷ lệ không di chuyển"] = table["ghost_rate"].map(lambda value: f"{value:.1%}")
    table["Khoảng cách ngắn nhất"] = table["min_gap_min"].map(lambda value: f"{value:.1f} phút")
    table["GMV trung bình"] = table["avg_gmv"].map(lambda value: f"{value:,.0f} đ")
    columns = {
        "Mức độ": "Mức độ",
        "driver_id": "Mã tài xế",
        "customer_id": "Mã khách hàng",
        "n_trips": "Số chuyến",
        "n_ghost": "Chuyến không di chuyển",
        "Tỷ lệ không di chuyển": "Tỷ lệ không di chuyển",
        "Khoảng cách ngắn nhất": "Khoảng cách ngắn nhất",
        "GMV trung bình": "GMV trung bình",
        "rule_score": "Điểm ưu tiên",
    }
    st.dataframe(
        table[list(columns)].rename(columns=columns).head(200),
        width="stretch",
        hide_index=True,
        column_config={"Điểm ưu tiên": st.column_config.ProgressColumn(min_value=0.0, max_value=1.0)},
    )

    st.subheader("Bản đồ mức độ bất thường")
    st.caption(
        "Càng sang trái: hai chuyến càng sát nhau. Càng lên trên: càng nhiều chuyến không di chuyển. "
        "Vòng tròn càng lớn: cặp đó đi cùng nhau càng nhiều."
    )
    chart_data = table.head(150)
    chart = px.scatter(
        chart_data,
        x="min_gap_min",
        y="ghost_rate",
        size="n_trips",
        color="Mức độ",
        color_discrete_map={"Nghiêm trọng": "#c2412d", "Cần theo dõi": "#d4a72c"},
        labels={
            "min_gap_min": "Khoảng cách ngắn nhất giữa hai chuyến (phút)",
            "ghost_rate": "Tỷ lệ chuyến không di chuyển",
            "n_trips": "Số chuyến",
        },
        hover_data={"driver_id": True, "customer_id": True, "rule_score": ":.2f"},
    )
    chart.add_vline(x=5, line_dash="dash", line_color="#8b8170")
    chart.add_hline(y=0.3, line_dash="dash", line_color="#8b8170")
    chart.update_layout(plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(chart, width="stretch")


def _render_detail(pairs: pd.DataFrame, reasons: pd.DataFrame, flags: pd.DataFrame) -> None:
    st.subheader("Tra cứu một cặp tài xế - khách hàng")
    st.caption("Chọn một cặp để xem lý do cảnh báo, các đơn liên quan, thời gian và địa điểm.")
    options = pairs.sort_values(
        ["high_confidence", "rule_score", "n_trips"], ascending=[False, False, False]
    ).assign(
        label=lambda frame: frame.apply(
            lambda row: (
                f"Tài xế {row['driver_id']} · Khách {row['customer_id']} · "
                f"{int(row['n_trips'])} chuyến · cách nhau {float(row['min_gap_min']):.1f} phút"
            ),
            axis=1,
        )
    )
    label = st.selectbox("Cặp cần xem", options["label"].head(200), label_visibility="collapsed")
    selected = options.loc[options["label"] == label].iloc[0]

    columns = st.columns(5)
    columns[0].metric("Tổng số chuyến", f"{int(selected['n_trips']):,}")
    columns[1].metric("Chuyến không di chuyển", f"{int(selected['n_ghost']):,}")
    columns[2].metric("Tỷ lệ không di chuyển", f"{float(selected['ghost_rate']):.1%}")
    columns[3].metric("Hai chuyến gần nhất", f"{float(selected['min_gap_min']):.1f} phút")
    columns[4].metric("GMV trung bình", f"{float(selected['avg_gmv']):,.0f} đ")

    pair_reasons = reasons[
        (reasons["driver_id"] == selected["driver_id"])
        & (reasons["customer_id"] == selected["customer_id"])
    ]
    if not pair_reasons.empty:
        readable_reasons = pair_reasons["reason_code"].map(REASON_NAMES).fillna(
            pair_reasons["reason_code"]
        )
        st.warning("Cặp này được cảnh báo vì: " + " · ".join(readable_reasons.unique()))

    orders = flags[
        (flags["driver_id"] == selected["driver_id"])
        & (flags["customer_id"] == selected["customer_id"])
    ].copy()
    if orders.empty:
        st.info("Không tìm thấy danh sách đơn của cặp này trong dữ liệu hiện tại.")
        return

    orders = orders.sort_values("order_time_local_tz", ascending=False)
    order_columns = {
        "order_id": "Mã đơn",
        "order_time_local_tz": "Thời gian đặt",
        "complete_time_local_tz": "Thời gian hoàn thành",
        "service_name": "Dịch vụ",
        "avg_kmh": "Tốc độ TB (km/h)",
        "gmv": "Giá trị đơn",
        "pickup_address": "Điểm đón",
        "last_dropoff_address": "Điểm trả",
    }
    available = [column for column in order_columns if column in orders.columns]
    st.subheader("Các đơn liên quan")
    st.dataframe(
        orders[available].rename(columns=order_columns).head(200),
        width="stretch",
        hide_index=True,
    )

    with st.expander("Xem trên đồ thị Neo4j (dành cho người phân tích)"):
        st.markdown(
            f"Mở Neo4j tại `{settings.neo4j_ride_browser_url}`, sau đó chạy câu truy vấn phù hợp."
        )
        query_names = {
            "Customer-driver repetition": "Toàn bộ đơn của cặp này",
            "Selected order details": "Chi tiết một đơn",
            "Customer timeline and linked drivers": "Khách hàng đã đi với những tài xế nào",
            "Driver timeline and linked customers": "Tài xế đã chở những khách hàng nào",
            "Pair route and time reuse": "Tuyến đường và thời gian bị lặp",
        }
        queries = build_neo4j_query_pack("REPEATED_CUSTOMER_DRIVER", orders.iloc[0])
        for key, title in query_names.items():
            if key in queries:
                st.markdown(f"**{title}**")
                st.code(queries[key], language="cypher")


def render_dashboard(report_dir: Path = REPORT_DIR) -> None:
    st.set_page_config(page_title="Theo dõi cuốc xe bất thường", page_icon="🚕", layout="wide")
    _apply_style()
    selected_report_dir = st.sidebar.text_input("Thư mục báo cáo", str(report_dir))
    reports = read_reports(selected_report_dir)
    daily = build_kbc_daily_summary(add_rule_display(reports["daily"]))
    flags = add_rule_display(reports["flags"])
    pairs = reports["kbc_pairs"]
    reasons = reports["kbc_reasons"]
    known_cases = reports["kbc_known"]

    st.title("Theo dõi cuốc xe bất thường")
    st.markdown(
        "Phát hiện các cặp **tài xế - khách hàng đi cùng nhau quá nhiều**, tạo cuốc quá nhanh "
        "hoặc có dấu hiệu cuốc không thực sự di chuyển."
    )
    if daily.empty or pairs.empty:
        st.warning("Chưa có dữ liệu báo cáo. Hãy chạy tác vụ cập nhật dữ liệu hằng ngày trước.")
        st.code("python -m scripts.build_task3_daily_outputs", language="powershell")
        return

    latest = _latest_date(flags)
    latest_text = latest.strftime("%d/%m/%Y") if latest else "chưa xác định"
    st.caption(f"Dữ liệu mới nhất: **{latest_text}** · KB-C: Cặp tài xế - khách hàng siêu tốc")

    filtered_pairs, filtered_reasons, filtered_flags = _filter_data(pairs, reasons, flags)
    if filtered_pairs.empty:
        st.info("Không có trường hợp phù hợp với bộ lọc. Hãy nới bộ lọc ở thanh bên trái.")
        return

    overview, review, detail, guide = st.tabs(
        ["Tổng quan", "Danh sách cần kiểm tra", "Tra cứu chi tiết", "Hướng dẫn"]
    )
    with overview:
        _render_overview(daily, filtered_pairs, filtered_reasons, filtered_flags)
    with review:
        _render_review(filtered_pairs)
    with detail:
        _render_detail(filtered_pairs, filtered_reasons, filtered_flags)
    with guide:
        st.subheader("Dashboard đang phát hiện điều gì?")
        st.markdown(
            "Hệ thống xem tài xế và khách hàng như hai đối tượng được nối với nhau bởi các chuyến xe. "
            "Liên kết trở nên đáng ngờ khi cặp đó có số chuyến thuộc nhóm cực hiếm, đồng thời có nhiều "
            "chuyến không di chuyển hoặc hai chuyến được tạo quá sát nhau."
        )
        st.dataframe(metric_guide(), width="stretch", hide_index=True)
        st.info(
            "**Ngưỡng nghiêm trọng:** tỷ lệ chuyến không di chuyển trên 30%, "
            "hoặc khoảng cách ngắn nhất giữa hai chuyến dưới 5 phút."
        )
        if not known_cases.empty:
            with st.expander("Kết quả kiểm tra với các trường hợp đã biết"):
                st.dataframe(known_cases, width="stretch", hide_index=True)
