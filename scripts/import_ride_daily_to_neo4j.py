"""Incrementally upsert daily ride orders into Neo4j."""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd
import pyarrow.parquet as pq

from src.config.settings import settings

if TYPE_CHECKING:
    from neo4j import Driver


RIDE_SOURCE_COLUMNS = [
    "order_id",
    "customer_id",
    "driver_id",
    "order_status",
    "cancel_by",
    "cancel_description",
    "order_time_local_tz",
    "complete_time_local_tz",
    "service_name",
    "service_type",
    "sub_vertical_name",
    "travel_mode",
    "channel_type",
    "is_now_order",
    "is_schedule_order",
    "declared_km",
    "actual_km",
    "km_ratio",
    "intrip_time_second",
    "avg_kmh",
    "gmv",
    "commission",
    "net_income",
    "discount",
    "rate_by_customer",
    "rate_by_driver",
    "payment_method",
    "promotion_code",
    "promotion_campaign_code",
    "pickup_province_name",
    "pickup_district_name",
    "pickup_address",
    "last_dropoff_province_name",
    "last_dropoff_district_name",
    "last_dropoff_address",
    "order_date",
]

ORDER_PROPERTY_SPECS: list[tuple[str, str, str]] = [
    ("order_id", "order_id", "string"),
    ("domain", "domain", "string"),
    ("order_status", "status", "string"),
    ("cancel_by", "cancel_by", "string"),
    ("cancel_description", "cancel_description", "string"),
    ("order_time_local_tz", "order_time", "datetime"),
    ("complete_time_local_tz", "completed_at", "datetime"),
    ("order_date", "order_date", "date"),
    ("service_name", "service_name", "string"),
    ("service_type", "service_type", "string"),
    ("sub_vertical_name", "sub_vertical_name", "string"),
    ("travel_mode", "travel_mode", "string"),
    ("channel_type", "channel_type", "string"),
    ("is_now_order", "is_now_order", "boolean"),
    ("is_schedule_order", "is_schedule_order", "boolean"),
    ("is_completed", "is_completed", "boolean"),
    ("declared_km", "declared_km", "float"),
    ("actual_km", "actual_km", "float"),
    ("km_ratio", "km_ratio", "float"),
    ("intrip_time_second", "intrip_time_second", "int"),
    ("avg_kmh", "avg_kmh", "float"),
    ("gmv", "gmv", "float"),
    ("commission", "commission", "float"),
    ("net_income", "net_income", "float"),
    ("discount", "discount", "float"),
    ("rate_by_customer", "rate_by_customer", "int"),
    ("rate_by_driver", "rate_by_driver", "int"),
]

UPSERT_RIDE_BATCH_CYPHER = """
UNWIND $rows AS row
MERGE (o:Order {order_id: row.order_id})
SET o += row.order_props
FOREACH (_ IN CASE WHEN row.customer_id IS NULL THEN [] ELSE [1] END |
  MERGE (c:Customer {customer_id: row.customer_id})
  MERGE (c)-[:PLACED]->(o)
)
FOREACH (_ IN CASE WHEN row.driver_id IS NULL THEN [] ELSE [1] END |
  MERGE (d:Driver {driver_id: row.driver_id})
  MERGE (d)-[:SERVED]->(o)
)
FOREACH (_ IN CASE WHEN row.pickup_address IS NULL THEN [] ELSE [1] END |
  MERGE (pickup:Address {address_key: row.pickup_address.address_key})
  SET pickup.address = row.pickup_address.address,
      pickup.district = row.pickup_address.district,
      pickup.province = row.pickup_address.province
  MERGE (o)-[:PICKUP_AT]->(pickup)
)
FOREACH (_ IN CASE WHEN row.dropoff_address IS NULL THEN [] ELSE [1] END |
  MERGE (dropoff:Address {address_key: row.dropoff_address.address_key})
  SET dropoff.address = row.dropoff_address.address,
      dropoff.district = row.dropoff_address.district,
      dropoff.province = row.dropoff_address.province
  MERGE (o)-[:DROPOFF_AT]->(dropoff)
)
FOREACH (_ IN CASE WHEN row.payment_method IS NULL THEN [] ELSE [1] END |
  MERGE (pm:PaymentMethod {name: row.payment_method})
  MERGE (o)-[:PAID_BY]->(pm)
)
FOREACH (_ IN CASE WHEN row.promotion_code IS NULL THEN [] ELSE [1] END |
  MERGE (promo:PromotionCode {code: row.promotion_code})
  MERGE (o)-[:USED_PROMO]->(promo)
)
FOREACH (_ IN CASE WHEN row.promotion_code IS NULL OR row.promotion_campaign_code IS NULL THEN [] ELSE [1] END |
  MERGE (promo:PromotionCode {code: row.promotion_code})
  MERGE (campaign:PromotionCampaign {code: row.promotion_campaign_code})
  MERGE (promo)-[:IN_CAMPAIGN]->(campaign)
)
FOREACH (_ IN CASE WHEN row.cancel_by IS NULL THEN [] ELSE [1] END |
  MERGE (actor:CancelActor {name: row.cancel_by})
  MERGE (o)-[:CANCELLED_BY]->(actor)
)
FOREACH (_ IN CASE WHEN row.cancel_description IS NULL THEN [] ELSE [1] END |
  MERGE (reason:CancelReason {reason: row.cancel_description})
  MERGE (o)-[:HAS_CANCEL_REASON]->(reason)
)
FOREACH (_ IN CASE WHEN row.service_name IS NULL THEN [] ELSE [1] END |
  MERGE (service:RideService {name: row.service_name})
  MERGE (o)-[:USES_SERVICE]->(service)
)
FOREACH (_ IN CASE WHEN row.service_type IS NULL THEN [] ELSE [1] END |
  MERGE (serviceType:ServiceType {name: row.service_type})
  MERGE (o)-[:USES_SERVICE_TYPE]->(serviceType)
)
FOREACH (_ IN CASE WHEN row.sub_vertical_name IS NULL THEN [] ELSE [1] END |
  MERGE (subVertical:SubVertical {name: row.sub_vertical_name})
  MERGE (o)-[:USES_SUB_VERTICAL]->(subVertical)
)
FOREACH (_ IN CASE WHEN row.travel_mode IS NULL THEN [] ELSE [1] END |
  MERGE (travelMode:TravelMode {name: row.travel_mode})
  MERGE (o)-[:USES_TRAVEL_MODE]->(travelMode)
)
FOREACH (_ IN CASE WHEN row.channel_type IS NULL THEN [] ELSE [1] END |
  MERGE (channelType:ChannelType {name: row.channel_type})
  MERGE (o)-[:USES_CHANNEL_TYPE]->(channelType)
)
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Incrementally import daily ride orders into Neo4j."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("data/handoff/ride/cleaned_orders/orders_ride_masked_2026-07-2[4-9].parquet"),
        help="Ride cleaned-orders file in parquet or csv format.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=2_000,
        help="Read and write batch size for Neo4j upserts.",
    )
    parser.add_argument(
        "--cypher",
        type=Path,
        default=Path("src/graph/cypher/001_constraints.cypher"),
        help="Cypher file that defines required constraints and indexes.",
    )
    parser.add_argument(
        "--wait-seconds",
        type=int,
        default=180,
        help="Seconds to wait for Neo4j to become reachable.",
    )
    return parser.parse_args()


def normalize_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = unicodedata.normalize("NFKC", str(value)).casefold().strip()
    return " ".join(text.split())


def optional_string(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def optional_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def optional_int(value: object) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(value)


def optional_bool(value: object) -> bool | None:
    if value is None or pd.isna(value):
        return None
    return bool(value)


def optional_datetime(value: object) -> datetime | None:
    if value is None or pd.isna(value):
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime()


def optional_date(value: object) -> date | None:
    if value is None or pd.isna(value):
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date()


def is_completed_status(value: object) -> bool:
    return optional_string(value) == "COMPLETED"


def build_address_payload(
    province: object,
    district: object,
    address: object,
) -> dict[str, str | None] | None:
    normalized_address = normalize_text(address)
    if not normalized_address:
        return None
    canonical = "|".join(
        (normalize_text(province), normalize_text(district), normalized_address)
    )
    return {
        "address_key": hashlib.sha1(canonical.encode("utf-8")).hexdigest(),
        "address": optional_string(address),
        "district": optional_string(district),
        "province": optional_string(province),
    }


def split_cypher(script: str) -> list[str]:
    return [statement.strip() for statement in script.split(";") if statement.strip()]


def wait_for_driver(wait_seconds: int) -> Driver:
    from neo4j import GraphDatabase

    deadline = time.monotonic() + wait_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
        )
        try:
            driver.verify_connectivity()
            return driver
        except Exception as error:
            last_error = error
            driver.close()
            time.sleep(3)
    raise TimeoutError(f"Neo4j was not ready after {wait_seconds}s: {last_error}")


def ensure_constraints(driver: Driver, cypher_path: Path, database: str | None = None) -> None:
    target_database = database or settings.neo4j_database
    for statement in split_cypher(cypher_path.read_text(encoding="utf-8")):
        driver.execute_query(statement, database_=target_database)


def source_batches(path: Path, batch_size: int) -> tuple[int, Any]:
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        parquet_file = pq.ParquetFile(path)
        return parquet_file.metadata.num_rows, parquet_file.iter_batches(
            batch_size=batch_size,
            columns=RIDE_SOURCE_COLUMNS,
            use_threads=True,
        )
    if suffix == ".csv":
        row_count = max(sum(1 for _ in path.open("r", encoding="utf-8")) - 1, 0)
        return row_count, pd.read_csv(path, chunksize=batch_size)
    raise ValueError(f"Unsupported ride source format: {path.suffix}")


def batch_to_frame(batch: Any) -> pd.DataFrame:
    if hasattr(batch, "to_pandas"):
        return batch.to_pandas()
    return batch


def normalize_ride_frame(frame: pd.DataFrame) -> pd.DataFrame:
    working = frame.copy()
    for column in RIDE_SOURCE_COLUMNS:
        if column not in working.columns:
            working.loc[:, column] = pd.NA
    if "is_completed" not in working.columns:
        working.loc[:, "is_completed"] = working["order_status"].map(is_completed_status)
    working.loc[:, "domain"] = "ride"
    working.loc[:, "order_id"] = working["order_id"].astype("string").str.strip()
    working = working[working["order_id"].notna() & working["order_id"].ne("")]
    return working.reset_index(drop=True)


def summarize_quality_checks(frame: pd.DataFrame) -> dict[str, int]:
    return {
        "missing_order_id": int(frame["order_id"].isna().sum()) if "order_id" in frame.columns else len(frame),
        "missing_customer_id": int(frame["customer_id"].isna().sum()) if "customer_id" in frame.columns else len(frame),
        "missing_order_time_local_tz": int(frame["order_time_local_tz"].isna().sum()) if "order_time_local_tz" in frame.columns else len(frame),
        "duplicate_order_id": int(frame.duplicated(["order_id"]).sum()) if "order_id" in frame.columns else len(frame),
    }


def build_order_props(row: pd.Series) -> dict[str, object]:
    props: dict[str, object] = {}
    for source, target, kind in ORDER_PROPERTY_SPECS:
        value = row.get(source)
        if kind == "string":
            props[target] = optional_string(value)
        elif kind == "float":
            props[target] = optional_float(value)
        elif kind == "int":
            props[target] = optional_int(value)
        elif kind == "boolean":
            props[target] = optional_bool(value)
        elif kind == "datetime":
            props[target] = optional_datetime(value)
        elif kind == "date":
            props[target] = optional_date(value)
        else:
            raise ValueError(f"Unsupported property kind: {kind}")
    return props


def prepare_ride_rows(frame: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        order_id = optional_string(row.get("order_id"))
        if order_id is None:
            continue
        rows.append(
            {
                "order_id": order_id,
                "customer_id": optional_string(row.get("customer_id")),
                "driver_id": optional_string(row.get("driver_id")),
                "payment_method": optional_string(row.get("payment_method")),
                "promotion_code": optional_string(row.get("promotion_code")),
                "promotion_campaign_code": optional_string(row.get("promotion_campaign_code")),
                "cancel_by": optional_string(row.get("cancel_by")),
                "cancel_description": optional_string(row.get("cancel_description")),
                "service_name": optional_string(row.get("service_name")),
                "service_type": optional_string(row.get("service_type")),
                "sub_vertical_name": optional_string(row.get("sub_vertical_name")),
                "travel_mode": optional_string(row.get("travel_mode")),
                "channel_type": optional_string(row.get("channel_type")),
                "pickup_address": build_address_payload(
                    row.get("pickup_province_name"),
                    row.get("pickup_district_name"),
                    row.get("pickup_address"),
                ),
                "dropoff_address": build_address_payload(
                    row.get("last_dropoff_province_name"),
                    row.get("last_dropoff_district_name"),
                    row.get("last_dropoff_address"),
                ),
                "order_props": build_order_props(row),
            }
        )
    return rows


def existing_order_ids(driver: Driver, order_ids: list[str]) -> set[str]:
    if not order_ids:
        return set()
    records, _, _ = driver.execute_query(
        "MATCH (o:Order) WHERE o.order_id IN $order_ids RETURN o.order_id AS order_id",
        order_ids=order_ids,
        database_=settings.neo4j_database,
    )
    return {record["order_id"] for record in records}


def import_batches(driver: Driver, source: Path, batch_size: int) -> dict[str, int]:
    expected_rows, batches = source_batches(source, batch_size)
    if expected_rows <= 0:
        raise RuntimeError("Ride source data is empty")

    counters = {
        "source_rows": expected_rows,
        "processed_rows": 0,
        "valid_rows": 0,
        "new_orders": 0,
        "updated_orders": 0,
        "missing_order_id": 0,
        "missing_customer_id": 0,
        "missing_order_time_local_tz": 0,
        "duplicate_order_id": 0,
    }

    for batch_number, batch in enumerate(batches, start=1):
        raw_frame = batch_to_frame(batch)
        counters["processed_rows"] += len(raw_frame)
        for check_name, count in summarize_quality_checks(raw_frame).items():
            counters[check_name] += count

        frame = normalize_ride_frame(raw_frame)
        if frame.empty:
            print(
                f"batch={batch_number} processed={counters['processed_rows']:,} valid_rows=0 skipped_blank_order_id=all",
                flush=True,
            )
            continue

        frame = frame.drop_duplicates(subset=["order_id"], keep="first").reset_index(drop=True)
        rows = prepare_ride_rows(frame)
        if not rows:
            continue

        order_ids = [row["order_id"] for row in rows]
        existing = existing_order_ids(driver, order_ids)
        counters["valid_rows"] += len(rows)
        counters["updated_orders"] += len(existing)
        counters["new_orders"] += len(rows) - len(existing)

        driver.execute_query(
            UPSERT_RIDE_BATCH_CYPHER,
            rows=rows,
            database_=settings.neo4j_database,
        )
        print(
            f"batch={batch_number} processed={counters['processed_rows']:,} "
            f"valid_rows={len(rows):,} new_orders={counters['new_orders']:,} "
            f"updated_orders={counters['updated_orders']:,}",
            flush=True,
        )

    if counters["processed_rows"] != counters["source_rows"]:
        raise RuntimeError(
            f"Processed {counters['processed_rows']} rows; expected {counters['source_rows']}"
        )
    return counters


def main() -> int:
    args = parse_args()
    source = args.source.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)

    driver = wait_for_driver(args.wait_seconds)
    try:
        ensure_constraints(driver, args.cypher.resolve(), settings.neo4j_database)
        counters = import_batches(driver, source, args.batch_size)
    finally:
        driver.close()

    print(f"Source rows: {counters['source_rows']:,}")
    print(f"Valid imported rows: {counters['valid_rows']:,}")
    print(f"New orders: {counters['new_orders']:,}")
    print(f"Updated orders: {counters['updated_orders']:,}")
    print(f"Missing order_id rows: {counters['missing_order_id']:,}")
    print(f"Missing customer_id rows: {counters['missing_customer_id']:,}")
    print(f"Missing order_time rows: {counters['missing_order_time_local_tz']:,}")
    print(f"Duplicate order_id rows in source: {counters['duplicate_order_id']:,}")
    print("Ride daily import completed")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
