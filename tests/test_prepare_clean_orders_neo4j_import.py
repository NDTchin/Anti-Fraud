from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from scripts.prepare_clean_orders_neo4j_import import (
    HEADERS,
    build_address_keys,
    clean_id_values,
    deduplicate_new_orders,
    normalize_order_frame,
    quality_report,
    read_sql_source,
    source_batches,
)


def test_clean_id_values_removes_null_and_empty_values() -> None:
    values = clean_id_values(pd.Series([" c1 ", "", None, "c2"]))

    assert values == {"c1", "c2"}


def test_build_address_keys_is_stable_for_equivalent_text() -> None:
    frame = pd.DataFrame(
        {
            "province": ["TP HCM", "tp hcm"],
            "district": [" Quan 1 ", "quan 1"],
            "address": ["  1 Nguyen Hue", "1   Nguyen Hue "],
        }
    )
    addresses: dict[str, tuple[str | None, str | None, str | None, str]] = {}
    cache: dict[str, str] = {}

    keys = build_address_keys(frame, "province", "district", "address", addresses, cache)

    assert len(set(keys)) == 1
    assert len(addresses) == 1


def test_normalize_order_frame_adds_domain_and_missing_columns() -> None:
    frame = pd.DataFrame(
        {
            "order_id": ["o1"],
            "order_status": ["COMPLETED"],
            "order_time_local_tz": ["2026-07-14 10:01:02"],
            "km_ratio": [1.25],
        }
    )

    normalized = normalize_order_frame(frame, "food")

    assert normalized.loc[0, "domain"] == "food"
    assert normalized.loc[0, "order_time_local_tz"] == "2026-07-14T10:01:02"
    assert bool(normalized.loc[0, "is_completed"]) is True
    assert normalized.loc[0, "km_ratio"] == 1.25
    assert "merchant_id" not in normalized.columns


def test_deduplicate_new_orders_skips_existing_order_ids() -> None:
    frame = pd.DataFrame(
        {
            "order_id": ["o1", "o2", "o2", "o3"],
            "customer_id": ["c1", "c2", "c2_dup", "c3"],
        }
    )

    deduplicated, new_order_ids = deduplicate_new_orders(frame, {"o1"})

    assert deduplicated["order_id"].tolist() == ["o2", "o3"]
    assert new_order_ids == {"o2", "o3"}


def test_quality_report_counts_missing_required_fields() -> None:
    frame = pd.DataFrame(
        {
            "order_id": ["o1", "o1"],
            "customer_id": ["c1", None],
            "order_time_local_tz": ["2026-07-14", None],
        }
    )

    report = quality_report(frame, "food")
    checks = {row["check_name"]: row["failed_rows"] for row in report}

    assert checks["missing_customer_id"] == 1
    assert checks["missing_order_time_local_tz"] == 1
    assert checks["duplicate_order_id"] == 1




def test_read_sql_source_supports_sqlite_table_query() -> None:
    database_path = Path(r"D:\VSF\tmp_sql_test_read.db")
    if database_path.exists():
        database_path.unlink()
    with sqlite3.connect(database_path) as connection:
        pd.DataFrame(
            {
                "order_id": ["o1", "o2"],
                "customer_id": ["c1", "c2"],
                "order_time_local_tz": ["2026-07-14 10:00:00", "2026-07-14 11:00:00"],
            }
        ).to_sql("orders", connection, index=False, if_exists="replace")

    frame = read_sql_source(f"sqlite:///{database_path.as_posix()}", None, "orders")

    assert len(frame) == 2
    assert set(frame["order_id"]) == {"o1", "o2"}


def test_source_batches_supports_sql_sources() -> None:
    database_path = Path(r"D:\VSF\tmp_sql_test_batches.db")
    if database_path.exists():
        database_path.unlink()
    with sqlite3.connect(database_path) as connection:
        pd.DataFrame(
            {
                "order_id": ["o1"],
                "customer_id": ["c1"],
                "order_time_local_tz": ["2026-07-14 10:00:00"],
            }
        ).to_sql("orders", connection, index=False, if_exists="replace")

    expected_rows, batches = source_batches(
        None,
        batch_size=1000,
        sql_uri=f"sqlite:///{database_path.as_posix()}",
        sql_query="SELECT * FROM orders",
        sql_table=None,
    )

    batch = list(batches)[0]
    assert expected_rows == 1
    assert batch.loc[0, "order_id"] == "o1"


def test_headers_include_antifraud_entities_and_relationships() -> None:
    assert "cancel_actors" in HEADERS
    assert "cancel_reasons" in HEADERS
    assert "dropoff_fail_actors" in HEADERS
    assert "dropoff_fail_codes" in HEADERS
    assert "ride_services" in HEADERS
    assert "service_types" in HEADERS
    assert "sub_verticals" in HEADERS
    assert "travel_modes" in HEADERS
    assert "channel_types" in HEADERS
    assert "cancelled_by" in HEADERS
    assert "has_cancel_reason" in HEADERS
    assert "dropoff_failed_by" in HEADERS
    assert "has_dropoff_fail_code" in HEADERS
    assert "uses_service" in HEADERS
    assert "uses_service_type" in HEADERS
    assert "uses_sub_vertical" in HEADERS
    assert "uses_travel_mode" in HEADERS
    assert "uses_channel_type" in HEADERS
