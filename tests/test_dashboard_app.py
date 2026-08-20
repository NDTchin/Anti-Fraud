import sys
import types

import pandas as pd


streamlit_stub = types.ModuleType("streamlit")
streamlit_stub.cache_data = lambda *args, **kwargs: (lambda func: func)
plotly_stub = types.ModuleType("plotly")
plotly_express_stub = types.ModuleType("plotly.express")

sys.modules.setdefault("streamlit", streamlit_stub)
sys.modules.setdefault("plotly", plotly_stub)
sys.modules.setdefault("plotly.express", plotly_express_stub)

from src.dashboard.app import RULE_DISPLAY_NAMES, build_rule_cluster_summary, build_window_metrics


def test_repeated_customer_driver_summary_prioritizes_kbc_signals() -> None:
    rule_flags = pd.DataFrame(
        [
            {
                "order_id": "o1",
                "customer_id": "c1",
                "driver_id": "d1",
                "reason_code": "KB-C",
                "pair_core_score": 66.65,
                "network_support_score": 82.78,
                "priority_score": 72.3,
                "n_trips": 64,
                "n_ghost": 20,
                "min_gap_min": 0.9,
                "ghost_rate": 20 / 64,
                "high_confidence": True,
                "avg_gmv": 12390.0,
                "supporting_signal_count": 4,
                "linked_pair_count": 6,
                "component_size": 7,
                "component_density": 0.57,
                "risk_tier": "HIGH",
            },
            {
                "order_id": "o2",
                "customer_id": "c1",
                "driver_id": "d1",
                "reason_code": "KB-C",
                "pair_core_score": 66.65,
                "network_support_score": 80.0,
                "priority_score": 71.0,
                "n_trips": 64,
                "n_ghost": 20,
                "min_gap_min": 1.2,
                "ghost_rate": 20 / 64,
                "high_confidence": True,
                "avg_gmv": 12390.0,
                "supporting_signal_count": 4,
                "linked_pair_count": 6,
                "component_size": 7,
                "component_density": 0.57,
                "risk_tier": "HIGH",
            },
            {
                "order_id": "o3",
                "customer_id": "c2",
                "driver_id": "d2",
                "reason_code": "KB-C",
                "pair_core_score": 43.0,
                "network_support_score": 50.0,
                "priority_score": 45.0,
                "n_trips": 13,
                "n_ghost": 1,
                "min_gap_min": 8.0,
                "ghost_rate": 1 / 13,
                "high_confidence": False,
                "avg_gmv": 45000.0,
                "supporting_signal_count": 1,
                "linked_pair_count": 1,
                "component_size": 2,
                "component_density": 1.0,
                "risk_tier": "WATCHLIST",
            },
        ]
    )

    summary = build_rule_cluster_summary(rule_flags, "REPEATED_CUSTOMER_DRIVER")

    assert summary.iloc[0]["customer_id"] == "c1"
    assert summary.iloc[0]["driver_id"] == "d1"
    assert summary.iloc[0]["flagged_orders"] == 2
    assert summary.iloc[0]["max_n_trips"] == 64
    assert summary.iloc[0]["max_n_ghost"] == 20
    assert summary.iloc[0]["min_gap_min"] == 0.9
    assert summary.iloc[0]["max_ghost_rate"] == 20 / 64
    assert bool(summary.iloc[0]["high_confidence"]) is True
    assert summary.iloc[0]["avg_gmv"] == 12390.0
    assert summary.iloc[0]["avg_pair_core_score"] == 66.65
    assert summary.iloc[0]["avg_network_support_score"] == 81.39
    assert summary.iloc[0]["max_priority_score"] == 72.3
    assert summary.iloc[0]["max_supporting_signal_count"] == 4
    assert summary.iloc[0]["max_linked_pair_count"] == 6
    assert summary.iloc[0]["max_component_size"] == 7
    assert summary.iloc[0]["top_risk_tier"] == "HIGH"


def test_repeated_customer_driver_display_name_reflects_kbc_scope() -> None:
    assert RULE_DISPLAY_NAMES["REPEATED_CUSTOMER_DRIVER"] == "Danh sach cap tai xe - khach hang can xem"


def test_window_metrics_use_latest_available_data_date() -> None:
    flags = pd.DataFrame(
        [
            {
                "order_id": "o1",
                "order_date": "2026-07-14",
                "driver_id": "d1",
                "customer_id": "c1",
                "high_confidence": True,
                "risk_tier": "HIGH",
            },
            {
                "order_id": "o2",
                "order_date": "2026-07-17",
                "driver_id": "d1",
                "customer_id": "c1",
                "high_confidence": True,
                "risk_tier": "WATCHLIST",
            },
        ]
    )

    windows = build_window_metrics(flags).set_index("window_label")

    assert windows.loc["1D", "flagged_orders"] == 1
    assert windows.loc["7D", "flagged_orders"] == 2
    assert windows.loc["1D", "watchlist_orders"] == 1
    assert windows.loc["7D", "high_risk_orders"] == 1
    assert str(windows.loc["1D", "start_date"]) == "2026-07-17"
    assert str(windows.loc["1D", "end_date"]) == "2026-07-17"
