"""User-facing dashboard aligned to the pair-core -> WCC workflow."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

try:
    import plotly.express as px
except ModuleNotFoundError:  # pragma: no cover
    px = None

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
    "KB-C_EXTREME_VOLUME": "Di cung nhau qua nhieu lan",
    "KB-C_TIGHT_PAIR_SHARE": "Tai xe va khach hang phu thuoc manh vao nhau",
    "KB-C_SUSPICIOUS_COMPONENT": "Nam trong nhom lien ket dang chu y",
    "KB-C_HIGH_GHOST_RATE": "Nhieu chuyen co dau hieu khong di chuyen",
    "KB-C_SUPERFAST_GAP": "Hai chuyen lap lai qua sat nhau",
    "KB-C_ROUTE_LOOP": "Lap lai cung mot tuyen duong",
}

RISK_TIER_ORDER = ["IMMEDIATE_REVIEW", "HIGH_RISK", "MONITOR", "LOW_PRIORITY"]
RISK_TIER_LABELS = {
    "IMMEDIATE_REVIEW": "Dieu tra ngay",
    "HIGH_RISK": "Rui ro cao",
    "MONITOR": "Can theo doi",
    "LOW_PRIORITY": "Theo doi thap",
}


def _plot_or_table(title: str, frame: pd.DataFrame, plotter) -> None:
    st.caption(title)
    if frame.empty:
        st.info("Khong co du lieu de hien thi o muc nay.")
        return
    if px is None:
        st.dataframe(frame, width="stretch", hide_index=True)
        return
    fig = plotter(frame)
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, width="stretch")


def _apply_style() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(214, 137, 16, 0.10), transparent 28%),
                linear-gradient(180deg, #f7f2e7 0%, #fffdf8 360px, #ffffff 100%);
        }
        .block-container {padding-top: 2rem; padding-bottom: 4rem;}
        [data-testid="stMetric"] {
            background: rgba(255,255,255,0.92);
            border: 1px solid #eadfca;
            border-radius: 16px;
            padding: 16px 18px;
            box-shadow: 0 12px 28px rgba(69, 50, 22, 0.07);
        }
        [data-testid="stMetricLabel"] {color: #7a6850;}
        [data-testid="stMetricValue"] {color: #173f35;}
        .user-card {
            background: linear-gradient(135deg, #fffdf8 0%, #fff7eb 100%);
            border: 1px solid #eadfca;
            border-radius: 18px;
            padding: 18px 20px;
            margin-bottom: 1rem;
            box-shadow: 0 12px 28px rgba(69, 50, 22, 0.06);
        }
        .user-card h4 {
            margin: 0 0 8px 0;
            color: #8a4b17;
            font-size: 1rem;
        }
        .user-card p {
            margin: 0;
            color: #4e4335;
            line-height: 1.5;
        }
        div[data-testid="stTabs"] button {
            font-size: 1rem;
            font-weight: 650;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _latest_date(flags: pd.DataFrame) -> object | None:
    if flags.empty or "order_date" not in flags.columns:
        return None
    parsed = pd.to_datetime(flags["order_date"], errors="coerce").dropna()
    return parsed.max().date() if not parsed.empty else None


def _score_column(frame: pd.DataFrame) -> str | None:
    return "priority_score" if "priority_score" in frame.columns else None


def _network_score_column(frame: pd.DataFrame) -> str | None:
    return "network_support_score" if "network_support_score" in frame.columns else None


def _sorted_pairs(pairs: pd.DataFrame) -> pd.DataFrame:
    if pairs.empty:
        return pairs.copy()
    sort_columns = [column for column in ("priority_score", "pair_core_score", "n_trips") if column in pairs.columns]
    return pairs.sort_values(sort_columns, ascending=[False] * len(sort_columns)).copy()


def _user_summary_cards(pairs: pd.DataFrame) -> list[dict[str, str]]:
    if pairs.empty:
        return []
    high_count = int(pairs["risk_tier"].eq("IMMEDIATE_REVIEW").sum()) if "risk_tier" in pairs.columns else 0
    component_max = int(pairs["component_size"].max()) if "component_size" in pairs.columns else 0
    avg_score = float(pairs["priority_score"].mean()) if "priority_score" in pairs.columns else 0.0
    return [
        {
            "title": "Tong quan",
            "body": f"Hien tai co {len(pairs):,} cap tai xe - khach hang dang can chu y. Trong do co {high_count:,} cap can xem ngay.",
        },
        {
            "title": "Cach he thong xep hang",
            "body": f"He thong uu tien xem truoc theo `priority_score`, trung binh hien tai la {avg_score:.1f}/100. Diem nay khong phai ket luan gian lan ma la thu tu review.",
        },
        {
            "title": "Nhin theo nhom",
            "body": (
                f"Mot so cap khong dung rieng le ma nam trong nhom lien ket toi da {component_max:,} cap."
                if component_max >= 3
                else "Da so truong hop hien tai van o muc cap doi tai xe - khach hang, phu hop de kiem tra theo tung cap."
            ),
        },
    ]


def _filter_data(
    pairs: pd.DataFrame,
    reasons: pd.DataFrame,
    flags: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    st.sidebar.header("Bo loc hien thi")
    st.sidebar.caption("Bo loc nay danh cho nguoi dung xem nhanh danh sach dang can chu y.")
    selected_tiers = st.sidebar.multiselect(
        "Muc do uu tien",
        options=RISK_TIER_ORDER,
        default=RISK_TIER_ORDER,
        format_func=lambda value: RISK_TIER_LABELS.get(value, value),
    )
    min_trips = int(pairs["n_trips"].min())
    max_trips = int(pairs["n_trips"].max())
    trip_cutoff = st.sidebar.slider("So chuyen toi thieu", min_trips, max_trips, min(6, max_trips))

    with st.sidebar.expander("Tuy chon bo loc them"):
        max_gap = min(10.0, float(pairs["min_gap_min"].max())) if "min_gap_min" in pairs.columns else 10.0
        gap_cutoff = st.slider("Khoang cach ngan nhat toi da (phut)", 0.0, max(10.0, max_gap), 5.0, 0.5)
        ghost_cutoff = st.slider("Ty le khong di chuyen toi thieu", 0.0, 1.0, 0.0, 0.05)
        max_score = float(pairs["priority_score"].max()) if "priority_score" in pairs.columns else 100.0
        score_cutoff = st.slider("Muc uu tien toi thieu", 0.0, max(100.0, max_score), 0.0, 1.0)

    filtered = pairs[pairs["n_trips"] >= trip_cutoff].copy()
    if "min_gap_min" in filtered.columns:
        filtered = filtered[filtered["min_gap_min"] <= gap_cutoff]
    if "ghost_rate" in filtered.columns:
        filtered = filtered[filtered["ghost_rate"] >= ghost_cutoff]
    if "risk_tier" in filtered.columns and selected_tiers:
        filtered = filtered[filtered["risk_tier"].isin(selected_tiers)]
    if "priority_score" in filtered.columns:
        filtered = filtered[filtered["priority_score"] >= score_cutoff]

    keys = filtered[["driver_id", "customer_id"]]
    filtered_reasons = reasons.merge(keys, on=["driver_id", "customer_id"], how="inner") if not reasons.empty else pd.DataFrame()
    filtered_flags = flags.merge(keys, on=["driver_id", "customer_id"], how="inner") if not flags.empty else pd.DataFrame()
    return filtered, filtered_reasons, filtered_flags


def _render_intro(pairs: pd.DataFrame) -> None:
    st.subheader("Ban dang nhin thay dieu gi?")
    for card in _user_summary_cards(pairs):
        st.markdown(
            f"""
            <div class="user-card">
              <h4>{card['title']}</h4>
              <p>{card['body']}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_overview(daily: pd.DataFrame, pairs: pd.DataFrame, reasons: pd.DataFrame, flags: pd.DataFrame) -> None:
    st.subheader("Tong quan nhanh")
    st.caption("Phan nay giup nguoi dung tra loi nhanh: co bao nhieu cap dang can chu y, cap nao nghiem trong hon, va co nam trong nhom lien ket lon hay khong.")

    windows = build_window_metrics(flags)
    if not windows.empty:
        labels = {"1D": "Gan nhat", "7D": "7 ngay", "30D": "30 ngay"}
        columns = st.columns(3)
        for index, row in windows.reset_index(drop=True).iterrows():
            columns[index].metric(labels[row["window_label"]], f"{int(row['flagged_orders']):,} don", help=f"Tu {row['start_date']} den {row['end_date']}")

    metrics = st.columns(5)
    metrics[0].metric("Cap dang chu y", f"{len(pairs):,}")
    metrics[1].metric("Dieu tra ngay", f"{int(pairs['risk_tier'].eq('IMMEDIATE_REVIEW').sum()):,}" if "risk_tier" in pairs.columns else "0")
    metrics[2].metric("Ty le ghost cao nhat", f"{float(pairs['ghost_rate'].max()):.0%}" if "ghost_rate" in pairs.columns and not pairs.empty else "n/a")
    metrics[3].metric("Muc tap trung cao nhat", f"{float(pairs['concentration_score'].max()):.2f}" if "concentration_score" in pairs.columns and not pairs.empty else "n/a")
    metrics[4].metric("Uu tien TB", f"{float(pairs['priority_score'].mean()):.1f}" if "priority_score" in pairs.columns and not pairs.empty else "n/a")

    st.info(
        "He thong di theo luong: tim repeated pair bat thuong, do muc do tap trung giua tai xe va khach hang, "
        "roi moi nhin xem cap do co duoc WCC/network support hay khong."
    )

    left, right = st.columns([3, 2])
    with left:
        _plot_or_table(
            "So don thuoc cac cap dang chu y theo ngay",
            daily,
            lambda frame: px.bar(frame, x="order_date", y="flagged_orders", text="flagged_orders", labels={"order_date": "Ngay", "flagged_orders": "So don"}, color_discrete_sequence=["#cf7b2a"]),
        )
    with right:
        summary = build_kbc_reason_pair_summary(reasons)
        if not summary.empty:
            summary["Ly do de y"] = summary["reason_code"].map(REASON_NAMES).fillna(summary["reason_code"])
            _plot_or_table(
                "Ly do cap bi dua vao danh sach can xem",
                summary[["Ly do de y", "flagged_pairs", "high_confidence_pairs", "avg_n_trips", "avg_ghost_rate"]],
                lambda frame: px.bar(frame, x="flagged_pairs", y="Ly do de y", orientation="h", labels={"flagged_pairs": "So cap"}, color_discrete_sequence=["#2f6c60"]),
            )

    graph_left, graph_right = st.columns(2)
    with graph_left:
        if "risk_tier" in pairs.columns:
            tier_summary = pairs.groupby("risk_tier", dropna=False).agg(pair_count=("driver_id", "size")).reset_index()
            tier_summary["risk_tier"] = pd.Categorical(tier_summary["risk_tier"], categories=RISK_TIER_ORDER, ordered=True)
            tier_summary = tier_summary.sort_values("risk_tier")
            _plot_or_table(
                "Phan bo theo muc do uu tien",
                tier_summary,
                lambda frame: px.bar(
                    frame,
                    x="risk_tier",
                    y="pair_count",
                    text="pair_count",
                    color="risk_tier",
                    color_discrete_map={
                        "IMMEDIATE_REVIEW": "#b9422c",
                        "HIGH_RISK": "#d4862e",
                        "MONITOR": "#cfb03f",
                        "LOW_PRIORITY": "#8ca17d",
                    },
                ),
            )
    with graph_right:
        if {"component_size", "linked_pair_count", "network_support_score", "priority_score"} <= set(pairs.columns):
            network_frame = _sorted_pairs(pairs).head(150)
            network_columns = ["driver_id", "customer_id", "linked_pair_count", "component_size", "priority_score", "network_support_score", "supporting_signal_count", "risk_tier"]
            network_columns = [column for column in network_columns if column in network_frame.columns]
            _plot_or_table(
                "Cap nao nam trong WCC component lon hon?",
                network_frame[network_columns],
                lambda frame: px.scatter(
                    frame,
                    x="linked_pair_count",
                    y="component_size",
                    size="priority_score",
                    color="risk_tier" if "risk_tier" in frame.columns else None,
                    hover_data=[column for column in ("driver_id", "customer_id", "network_support_score", "supporting_signal_count") if column in frame.columns],
                    color_discrete_map={
                        "IMMEDIATE_REVIEW": "#b9422c",
                        "HIGH_RISK": "#d4862e",
                        "MONITOR": "#cfb03f",
                        "LOW_PRIORITY": "#8ca17d",
                    },
                ),
            )


def _render_review(pairs: pd.DataFrame) -> None:
    st.subheader("Danh sach can xem")
    st.caption("Bang nay danh cho nguoi dung muon xem nhanh cap nao dang can uu tien truoc theo luong pair core roi moi den network support.")

    table = _sorted_pairs(pairs)
    table["Muc uu tien"] = table["risk_tier"].map(RISK_TIER_LABELS).fillna(table["risk_tier"]) if "risk_tier" in table.columns else "Can theo doi"
    if "ghost_rate" in table.columns:
        table["Ty le khong di chuyen"] = table["ghost_rate"].map(lambda value: f"{value:.1%}")
    if "avg_gmv" in table.columns:
        table["Gia tri trung binh"] = table["avg_gmv"].map(lambda value: f"{value:,.0f} d")

    columns = {
        "Muc uu tien": "Muc uu tien",
        "driver_id": "Ma tai xe",
        "customer_id": "Ma khach hang",
        "n_trips": "So chuyen",
        "concentration_score": "Muc do tap trung",
        "pair_core_score": "Diem pair core",
        "pair_risk_score": "Diem rui ro cap",
        "suspected_ghost_score": "Diem ghost",
        "network_support_score": "Diem lien ket",
        "business_impact_score": "Diem tac dong",
        "priority_score": "Diem uu tien",
        "linked_pair_count": "Cap lien ket",
        "component_size": "Kich thuoc nhom",
        "Ty le khong di chuyen": "Ty le khong di chuyen",
        "Gia tri trung binh": "Gia tri trung binh",
    }
    visible_columns = [column for column in columns if column in table.columns]
    st.dataframe(
        table[visible_columns].rename(columns=columns),
        width="stretch",
        hide_index=True,
        column_config={"Diem uu tien": st.column_config.ProgressColumn(min_value=0.0, max_value=100.0)},
    )

    if {"min_gap_min", "ghost_rate", "n_trips", "network_support_score", "priority_score"} <= set(table.columns):
        scatter_frame = table.head(150)
        scatter_columns = [column for column in ("driver_id", "customer_id", "min_gap_min", "ghost_rate", "priority_score", "risk_tier", "linked_pair_count", "network_support_score") if column in scatter_frame.columns]
        _plot_or_table(
            "Ban do muc do can chu y",
            scatter_frame[scatter_columns],
            lambda frame: px.scatter(
                frame,
                x="min_gap_min",
                y="ghost_rate",
                size="priority_score",
                color="risk_tier" if "risk_tier" in frame.columns else None,
                hover_data=[column for column in ("driver_id", "customer_id", "network_support_score", "linked_pair_count") if column in frame.columns],
                color_discrete_map={
                    "IMMEDIATE_REVIEW": "#b9422c",
                    "HIGH_RISK": "#d4862e",
                    "MONITOR": "#cfb03f",
                    "LOW_PRIORITY": "#8ca17d",
                },
            ).add_vline(x=5, line_dash="dash", line_color="#8b8170").add_hline(y=0.3, line_dash="dash", line_color="#8b8170"),
        )


def _render_detail(pairs: pd.DataFrame, reasons: pd.DataFrame, flags: pd.DataFrame) -> None:
    st.subheader("Xem chi tiet mot cap")
    st.caption("Phan nay danh cho nguoi dung muon mo mot cap cu the de xem tai sao he thong dua cap do vao suspicious pair list va cap do co duoc WCC support hay khong.")

    options = _sorted_pairs(pairs).assign(
        label=lambda frame: frame.apply(
            lambda row: f"Tai xe {row['driver_id']} | Khach {row['customer_id']} | {int(row['n_trips'])} chuyen | uu tien {float(row.get('priority_score', 0.0)):.1f}",
            axis=1,
        )
    )
    label = st.selectbox("Chon cap can xem", options["label"].head(200), label_visibility="collapsed")
    selected = options.loc[options["label"] == label].iloc[0]

    columns = st.columns(5)
    columns[0].metric("Tong so chuyen", f"{int(selected['n_trips']):,}")
    columns[1].metric("Ty le ghost", f"{float(selected.get('ghost_rate', 0.0)):.1%}")
    columns[2].metric("Muc do tap trung", f"{float(selected.get('concentration_score', 0.0)):.2f}")
    columns[3].metric("Pair core", f"{float(selected.get('pair_core_score', 0.0)):.1f}")
    columns[4].metric("Diem uu tien", f"{float(selected.get('priority_score', 0.0)):.1f}")

    graph_columns = st.columns(4)
    graph_columns[0].metric("Muc uu tien", str(RISK_TIER_LABELS.get(selected.get("risk_tier", ""), selected.get("risk_tier", "n/a"))))
    graph_columns[1].metric("Diem rui ro cap", f"{float(selected.get('pair_risk_score', 0.0)):.1f}")
    graph_columns[2].metric("Diem lien ket", f"{float(selected.get('network_support_score', 0.0)):.1f}")
    graph_columns[3].metric("Diem tac dong", f"{float(selected.get('business_impact_score', 0.0)):.1f}")

    pair_reasons = reasons[(reasons["driver_id"] == selected["driver_id"]) & (reasons["customer_id"] == selected["customer_id"])]
    if not pair_reasons.empty:
        readable_reasons = pair_reasons["reason_code"].map(REASON_NAMES).fillna(pair_reasons["reason_code"])
        st.markdown("**Vi sao cap nay duoc de y?**")
        for reason in readable_reasons.drop_duplicates().tolist():
            st.markdown(f"- {reason}")

    st.markdown(
        "Cap nay duoc xep hang tu 3 lop: bang chung repeated pair va concentration, "
        "ghost evidence/temporal pattern, va sau cung la support tu nhom lien ket WCC."
    )

    orders = flags[(flags["driver_id"] == selected["driver_id"]) & (flags["customer_id"] == selected["customer_id"])].copy()
    if orders.empty:
        st.info("Khong tim thay danh sach don lien quan trong du lieu hien tai.")
        return

    orders = orders.sort_values("order_time_local_tz", ascending=False)
    order_columns = {
        "order_id": "Ma don",
        "order_time_local_tz": "Thoi gian dat",
        "complete_time_local_tz": "Thoi gian hoan thanh",
        "service_name": "Dich vu",
        "avg_kmh": "Toc do TB (km/h)",
        "gmv": "Gia tri don",
        "reason_code": "Ly do de y",
        "pickup_address": "Diem don",
        "last_dropoff_address": "Diem tra",
    }
    available = [column for column in order_columns if column in orders.columns]
    st.subheader("Cac don lien quan")
    st.dataframe(orders[available].rename(columns=order_columns).head(200), width="stretch", hide_index=True)

    with st.expander("Phan ky thuat danh cho nhom van hanh/phan tich", expanded=False):
        st.markdown(f"Neo4j Browser: `{settings.neo4j_ride_browser_url}`")
        queries = build_neo4j_query_pack("REPEATED_CUSTOMER_DRIVER", orders.iloc[0])
        for title, query in queries.items():
            st.markdown(f"**{title}**")
            st.code(query, language="cypher")


def _render_guide(known_cases: pd.DataFrame) -> None:
    st.subheader("Huong dan doc dashboard")
    st.markdown(
        """
        - `Diem uu tien`: diem sap thu tu xem truoc, duoc tinh tu pair core roi moi cong them network support.
        - `Diem rui ro cap`: diem rui ro cua chinh cap tai xe - khach hang, da cong ghost evidence.
        - `Diem ghost`: muc do nghi ngo ghost-trip dua tren zero-speed rate, temporal gap va low-value pattern.
        - `Muc do tap trung`: cho biet tai xe va khach hang co dang phu thuoc bat thuong vao nhau hay khong.
        - `Kich thuoc nhom`: neu lon, cap do co the nam trong mot WCC component rong hon.
        - `Cap lien ket`: so suspicious pairs noi truc tiep voi cap hien tai qua shared entity.
        """
    )
    st.caption("Goc nhin ky thuat")
    st.dataframe(build_kbc_metric_guide(), width="stretch", hide_index=True)
    if not known_cases.empty:
        with st.expander("Ket qua doi chieu voi case da biet", expanded=False):
            st.dataframe(known_cases, width="stretch", hide_index=True)


def _render_components(components: pd.DataFrame) -> None:
    st.subheader("Nhom lien ket")
    st.caption("Moi dong la mot component sau khi da loc hub va yeu cau edge co du bang chung noi pair voi nhau.")
    if components.empty:
        st.info("Chua co du lieu component de hien thi.")
        return
    table = components.copy()
    if "component_risk_tier" in table.columns:
        table["component_risk_tier"] = table["component_risk_tier"].map(RISK_TIER_LABELS).fillna(table["component_risk_tier"])
    rename_map = {
        "component_id": "Ma nhom",
        "pair_count": "So cap",
        "driver_count": "So tai xe",
        "customer_count": "So khach hang",
        "high_risk_pair_count": "Cap rui ro cao",
        "high_risk_pair_ratio": "Ty le cap rui ro cao",
        "average_pair_score": "Diem TB",
        "maximum_pair_score": "Diem cao nhat",
        "component_density": "Mat do nhom",
        "network_risk_score": "Diem lien ket nhom",
        "component_risk_tier": "Uu tien nhom",
    }
    visible = [column for column in rename_map if column in table.columns]
    st.dataframe(table[visible].rename(columns=rename_map), width="stretch", hide_index=True)


def _render_graph_quality(graph_quality: pd.DataFrame, graph_signal_summary: pd.DataFrame) -> None:
    st.subheader("Chat luong network")
    st.caption("Phan nay danh cho analyst va data team kiem tra graph co dang bi noi qua rong boi hub hay khong.")
    if not graph_quality.empty:
        st.dataframe(graph_quality, width="stretch", hide_index=True)
    if not graph_signal_summary.empty:
        st.markdown("**Tong hop theo loai shared entity**")
        st.dataframe(graph_signal_summary, width="stretch", hide_index=True)


def render_dashboard(report_dir: Path = REPORT_DIR) -> None:
    st.set_page_config(page_title="Theo doi cuoc xe can chu y", page_icon=":taxi:", layout="wide")
    _apply_style()

    selected_report_dir = st.sidebar.text_input("Thu muc bao cao", str(report_dir))
    reports = read_reports(selected_report_dir)
    daily = build_kbc_daily_summary(add_rule_display(reports["daily"]))
    flags = add_rule_display(reports["flags"])
    pairs = reports["kbc_pairs"]
    reasons = reports["kbc_reasons"]
    known_cases = reports["kbc_known"]
    components = reports["kbc_components"]
    graph_quality = reports["graph_quality"]
    graph_signal_summary = reports["graph_signal_summary"]

    st.title("Tong quan cuoc xe can chu y")
    st.markdown(
        "Dashboard nay giup nguoi dung nhin nhanh cac cap **tai xe - khach hang** "
        "co dau hieu repeated pair bat thuong, muc do tap trung cao, va co the nam trong nhom lien ket dang de y."
    )
    if daily.empty or pairs.empty:
        st.warning("Chua co du lieu de hien thi. Hay chay build report truoc.")
        st.code("python -m scripts.build_task3_daily_outputs", language="powershell")
        return

    latest = _latest_date(flags)
    latest_text = latest.strftime("%d/%m/%Y") if latest else "chua xac dinh"
    st.caption(f"Du lieu moi nhat: **{latest_text}**")

    filtered_pairs, filtered_reasons, filtered_flags = _filter_data(pairs, reasons, flags)
    if filtered_pairs.empty:
        st.info("Khong co truong hop phu hop voi bo loc hien tai.")
        return

    _render_intro(filtered_pairs)

    overview, review, detail, components_tab, quality_tab, guide = st.tabs(
        ["Tong quan", "Danh sach can xem", "Xem chi tiet", "Nhom lien ket", "Chat luong mang", "Huong dan doc"]
    )
    with overview:
        _render_overview(daily, filtered_pairs, filtered_reasons, filtered_flags)
    with review:
        _render_review(filtered_pairs)
    with detail:
        _render_detail(filtered_pairs, filtered_reasons, filtered_flags)
    with components_tab:
        filtered_components = (
            components[components["component_id"].isin(filtered_pairs["component_id"].dropna().unique())]
            if not components.empty and "component_id" in components.columns and "component_id" in filtered_pairs.columns
            else components
        )
        _render_components(filtered_components)
    with quality_tab:
        _render_graph_quality(graph_quality, graph_signal_summary)
    with guide:
        _render_guide(known_cases)
