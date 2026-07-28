"""Prepare Neo4j import files from cleaned Food/Ride dashboard order tables."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import shutil
import sys
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


ORDER_FIELDS: list[tuple[str, str]] = [
    ("order_id:ID(Order-ID)", "order_id"),
    ("domain:string", "domain"),
    ("status:string", "order_status"),
    ("cancel_by:string", "cancel_by"),
    ("cancel_description:string", "cancel_description"),
    ("order_time:localdatetime", "order_time_local_tz"),
    ("completed_at:localdatetime", "complete_time_local_tz"),
    ("service_name:string", "service_name"),
    ("service_type:string", "service_type"),
    ("sub_vertical_name:string", "sub_vertical_name"),
    ("vertical_name:string", "vertical_name"),
    ("travel_mode:string", "travel_mode"),
    ("channel_type:string", "channel_type"),
    ("food_dispatch_type:string", "food_dispatch_type"),
    ("is_now_order:boolean", "is_now_order"),
    ("is_schedule_order:boolean", "is_schedule_order"),
    ("is_completed:boolean", "is_completed"),
    ("is_cancelled:boolean", "is_cancelled"),
    ("has_promotion:boolean", "has_promotion"),
    ("has_dropoff_fail:boolean", "has_dropoff_fail"),
    ("declared_km:double", "declared_km"),
    ("actual_km:double", "actual_km"),
    ("km_diff:double", "km_diff"),
    ("intrip_time_second:long", "intrip_time_second"),
    ("lead_time_second:long", "lead_time_second"),
    ("gmv:double", "gmv"),
    ("commission:double", "commission"),
    ("net_income:double", "net_income"),
    ("discount:double", "discount"),
    ("delivery_discount:double", "delivery_discount"),
    ("food_gmv:double", "food_gmv"),
    ("food_total_paid:double", "food_total_paid"),
    ("food_total_item_quantity:long", "food_total_item_quantity"),
    ("order_hour:long", "order_hour"),
    ("order_weekday:string", "order_weekday"),
    ("rate_by_customer:long", "rate_by_customer"),
    ("rate_by_driver:long", "rate_by_driver"),
]


HEADERS: dict[str, list[tuple[str, str]]] = {
    "orders": ORDER_FIELDS,
    "customers": [("customer_id:ID(Customer-ID)", "customer_id")],
    "drivers": [("driver_id:ID(Driver-ID)", "driver_id")],
    "merchants": [("merchant_id:ID(Merchant-ID)", "merchant_id")],
    "addresses": [
        ("address_key:ID(Address-ID)", "address_key"),
        ("address:string", "address"),
        ("district:string", "district"),
        ("province:string", "province"),
    ],
    "payment_methods": [("name:ID(Payment-ID)", "name")],
    "promotion_codes": [("code:ID(Promotion-ID)", "code")],
    "promotion_campaigns": [("code:ID(Campaign-ID)", "code")],
    "cancel_actors": [("name:ID(CancelActor-ID)", "name")],
    "cancel_reasons": [("reason:ID(CancelReason-ID)", "reason")],
    "dropoff_fail_actors": [("name:ID(DropoffFailActor-ID)", "name")],
    "dropoff_fail_codes": [("code:ID(DropoffFailCode-ID)", "code")],
    "ride_services": [("name:ID(RideService-ID)", "name")],
    "service_types": [("name:ID(ServiceType-ID)", "name")],
    "sub_verticals": [("name:ID(SubVertical-ID)", "name")],
    "travel_modes": [("name:ID(TravelMode-ID)", "name")],
    "channel_types": [("name:ID(ChannelType-ID)", "name")],
    "placed": [
        (":START_ID(Customer-ID)", "customer_id"),
        (":END_ID(Order-ID)", "order_id"),
    ],
    "served": [
        (":START_ID(Driver-ID)", "driver_id"),
        (":END_ID(Order-ID)", "order_id"),
    ],
    "from_merchant": [
        (":START_ID(Order-ID)", "order_id"),
        (":END_ID(Merchant-ID)", "merchant_id"),
    ],
    "pickup_at": [
        (":START_ID(Order-ID)", "order_id"),
        (":END_ID(Address-ID)", "address_key"),
    ],
    "dropoff_at": [
        (":START_ID(Order-ID)", "order_id"),
        (":END_ID(Address-ID)", "address_key"),
    ],
    "paid_by": [
        (":START_ID(Order-ID)", "order_id"),
        (":END_ID(Payment-ID)", "payment_method"),
    ],
    "used_promo": [
        (":START_ID(Order-ID)", "order_id"),
        (":END_ID(Promotion-ID)", "promotion_code"),
    ],
    "in_campaign": [
        (":START_ID(Promotion-ID)", "promotion_code"),
        (":END_ID(Campaign-ID)", "promotion_campaign_code"),
    ],
    "cancelled_by": [
        (":START_ID(Order-ID)", "order_id"),
        (":END_ID(CancelActor-ID)", "cancel_by"),
    ],
    "has_cancel_reason": [
        (":START_ID(Order-ID)", "order_id"),
        (":END_ID(CancelReason-ID)", "cancel_description"),
    ],
    "dropoff_failed_by": [
        (":START_ID(Order-ID)", "order_id"),
        (":END_ID(DropoffFailActor-ID)", "food_dropoff_fail_by"),
    ],
    "has_dropoff_fail_code": [
        (":START_ID(Order-ID)", "order_id"),
        (":END_ID(DropoffFailCode-ID)", "food_dropoff_fail_code"),
    ],
    "uses_service": [
        (":START_ID(Order-ID)", "order_id"),
        (":END_ID(RideService-ID)", "service_name"),
    ],
    "uses_service_type": [
        (":START_ID(Order-ID)", "order_id"),
        (":END_ID(ServiceType-ID)", "service_type"),
    ],
    "uses_sub_vertical": [
        (":START_ID(Order-ID)", "order_id"),
        (":END_ID(SubVertical-ID)", "sub_vertical_name"),
    ],
    "uses_travel_mode": [
        (":START_ID(Order-ID)", "order_id"),
        (":END_ID(TravelMode-ID)", "travel_mode"),
    ],
    "uses_channel_type": [
        (":START_ID(Order-ID)", "order_id"),
        (":END_ID(ChannelType-ID)", "channel_type"),
    ],
}


class ParquetSink:
    def __init__(
        self, path: Path, columns: list[str], stringify: bool = True
    ) -> None:
        self.path = path
        self.columns = columns
        self.stringify = stringify
        self.writer: pq.ParquetWriter | None = None
        self.rows = 0

    def write(self, frame: pd.DataFrame) -> None:
        clean = frame[self.columns].copy()
        clean = clean.dropna(subset=self.columns if self.stringify else ["order_id"])
        if self.stringify:
            for column in self.columns:
                clean[column] = clean[column].astype("string").str.strip()
            clean = clean[(clean != "").all(axis=1)]
        if clean.empty:
            return
        table = pa.Table.from_pandas(clean, preserve_index=False)
        if self.writer is None:
            self.writer = pq.ParquetWriter(
                self.path,
                table.schema,
                compression="zstd",
                use_dictionary=True,
            )
        self.writer.write_table(table)
        self.rows += len(clean)

    def close(self) -> None:
        if self.writer is not None:
            self.writer.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("data/orders_food_clean_dashboard.parquet"),
    )
    parser.add_argument(
        "--sql-uri",
        help="SQL connection URI, for example sqlite:///data/food_orders.db",
    )
    parser.add_argument(
        "--sql-query",
        help="SQL query used when reading directly from a SQL source",
    )
    parser.add_argument(
        "--sql-table",
        help="Table name used when reading directly from a SQL source",
    )
    parser.add_argument("--domain", choices=("food", "ride"), default="food")
    parser.add_argument("--output", type=Path, default=Path("data/neo4j-import/neo4j-import-output"))
    parser.add_argument("--batch-size", type=int, default=100_000)
    parser.add_argument("--minimum-free-gb", type=float, default=2.0)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def normalize(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = unicodedata.normalize("NFKC", str(value)).casefold().strip()
    return re.sub(r"\s+", " ", text)


def display(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def clean_id_values(series: pd.Series) -> set[str]:
    values = series.dropna().astype("string").str.strip()
    return set(values[values != ""])


def build_address_keys(
    frame: pd.DataFrame,
    province_column: str,
    district_column: str,
    address_column: str,
    addresses: dict[str, tuple[str | None, str | None, str | None, str]],
    cache: dict[str, str],
) -> list[str | None]:
    keys: list[str | None] = []
    rows = zip(
        frame.get(province_column, pd.Series([None] * len(frame))),
        frame.get(district_column, pd.Series([None] * len(frame))),
        frame.get(address_column, pd.Series([None] * len(frame))),
        strict=True,
    )
    for province, district, address in rows:
        normalized_address = normalize(address)
        if not normalized_address:
            keys.append(None)
            continue
        canonical = "|".join(
            (normalize(province), normalize(district), normalized_address)
        )
        key = cache.get(canonical)
        if key is None:
            key = hashlib.sha1(canonical.encode("utf-8")).hexdigest()
            cache[canonical] = key
            previous = addresses.get(key)
            if previous is not None and previous[3] != canonical:
                raise RuntimeError(f"SHA-1 collision for address key {key}")
            addresses[key] = (
                display(address),
                display(district),
                display(province),
                canonical,
            )
        keys.append(key)
    return keys


def write_headers(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, fields in HEADERS.items():
        with (directory / f"{name}.csv").open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.writer(handle)
            writer.writerow([field[0] for field in fields])
            writer.writerow([field[1] for field in fields])


def write_node_file(path: Path, data: dict[str, list[object]]) -> int:
    table = pa.Table.from_pydict(data)
    pq.write_table(table, path, compression="zstd", use_dictionary=True)
    return table.num_rows


def prepare_directories(output: Path, overwrite: bool) -> tuple[Path, Path]:
    marker = output / ".vsf-clean-orders-graph-import"
    generated = [output / "headers", output / "nodes", output / "relationships"]
    if any(path.exists() for path in generated):
        if not overwrite:
            raise FileExistsError(
                f"Generated import files already exist in {output}; use --overwrite"
            )
        if not marker.exists():
            raise RuntimeError(f"Refusing to overwrite unrecognized directory: {output}")
        for path in generated:
            if path.exists():
                shutil.rmtree(path)
    headers = output / "headers"
    nodes = output / "nodes"
    relationships = output / "relationships"
    nodes.mkdir(parents=True, exist_ok=True)
    relationships.mkdir(parents=True, exist_ok=True)
    marker.touch()
    write_headers(headers)
    return nodes, relationships


def read_sql_source(
    sql_uri: str, sql_query: str | None, sql_table: str | None
) -> pd.DataFrame:
    query = sql_query
    if query is None and sql_table:
        query = f"SELECT * FROM {sql_table}"
    if not query:
        raise ValueError("SQL input requires --sql-query or --sql-table")

    parsed = urlparse(sql_uri)
    if parsed.scheme == "sqlite":
        raw_path = f"{parsed.netloc}{parsed.path}"
        if raw_path in ("", ":memory:"):
            database = raw_path or ":memory:"
        else:
            if raw_path.startswith("/") and len(raw_path) >= 3 and raw_path[2] == ":":
                raw_path = raw_path[1:]
            database = str(Path(unquote(raw_path)).expanduser())
        with sqlite3.connect(database) as connection:
            return pd.read_sql_query(query, connection)

    try:
        from sqlalchemy import create_engine
    except ImportError as error:
        raise ImportError(
            "Reading non-sqlite SQL sources requires SQLAlchemy. "
            "Install it with `python -m pip install sqlalchemy`."
        ) from error

    engine = create_engine(sql_uri)
    try:
        with engine.connect() as connection:
            return pd.read_sql_query(query, connection)
    finally:
        engine.dispose()


def source_batches(
    path: Path | None,
    batch_size: int,
    sql_uri: str | None,
    sql_query: str | None,
    sql_table: str | None,
) -> tuple[int, Any]:
    if sql_uri:
        frame = read_sql_source(sql_uri, sql_query, sql_table)
        return len(frame), [frame]
    if path is None:
        raise ValueError("A file source or SQL source is required")
    if path.suffix.lower() == ".parquet":
        parquet_file = pq.ParquetFile(path)
        return parquet_file.metadata.num_rows, parquet_file.iter_batches(
            batch_size=batch_size,
            use_threads=True,
        )
    if path.suffix.lower() == ".csv":
        row_count = sum(1 for _ in path.open("r", encoding="utf-8")) - 1
        chunks = pd.read_csv(path, chunksize=batch_size)
        return row_count, chunks
    raise ValueError(f"Unsupported source format: {path.suffix}")


def batch_to_frame(batch: Any) -> pd.DataFrame:
    if hasattr(batch, "to_pandas"):
        return batch.to_pandas()
    return batch


def add_missing_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        if column not in frame.columns:
            frame[column] = pd.NA
    return frame


def normalize_order_frame(frame: pd.DataFrame, domain: str) -> pd.DataFrame:
    frame = frame.copy()
    frame["domain"] = domain
    target_columns = [source for _, source in ORDER_FIELDS]
    add_missing_columns(frame, target_columns)
    for column in (
        "order_time_local_tz",
        "complete_time_local_tz",
    ):
        values = pd.to_datetime(frame[column], errors="coerce")
        frame[column] = values.dt.strftime("%Y-%m-%dT%H:%M:%S")
    bool_columns = [
        "is_now_order",
        "is_schedule_order",
        "is_completed",
        "is_cancelled",
        "has_promotion",
        "has_dropoff_fail",
    ]
    for column in bool_columns:
        frame[column] = frame[column].astype("boolean")
    return frame[target_columns]


def quality_report(frame: pd.DataFrame, domain: str) -> list[dict[str, object]]:
    required = ("order_id", "customer_id", "order_time_local_tz")
    checks = []
    for column in required:
        missing = len(frame) if column not in frame else int(frame[column].isna().sum())
        checks.append({"domain": domain, "check_name": f"missing_{column}", "failed_rows": missing})
    duplicated = int(frame.duplicated(["order_id"]).sum()) if "order_id" in frame else len(frame)
    checks.append({"domain": domain, "check_name": "duplicate_order_id", "failed_rows": duplicated})
    return checks


def main() -> int:
    args = parse_args()
    source = args.source.resolve() if args.sql_uri is None else None
    output = args.output.resolve()
    if source is not None and not source.is_file():
        raise FileNotFoundError(source)

    output.mkdir(parents=True, exist_ok=True)
    free_gb = shutil.disk_usage(output).free / (1024**3)
    if free_gb < args.minimum_free_gb:
        raise RuntimeError(
            f"Only {free_gb:.1f} GB free on {output.drive}; "
            f"at least {args.minimum_free_gb:.1f} GB is required"
        )

    expected_rows, batches = source_batches(
        source,
        args.batch_size,
        args.sql_uri,
        args.sql_query,
        args.sql_table,
    )
    if expected_rows <= 0:
        raise RuntimeError("Source data is empty")

    nodes_dir, relationships_dir = prepare_directories(output, args.overwrite)
    order_sink = ParquetSink(
        nodes_dir / "orders.parquet",
        [source for _, source in ORDER_FIELDS],
        stringify=False,
    )
    relationship_sinks = {
        "placed": ParquetSink(relationships_dir / "placed.parquet", ["customer_id", "order_id"]),
        "served": ParquetSink(relationships_dir / "served.parquet", ["driver_id", "order_id"]),
        "from_merchant": ParquetSink(
            relationships_dir / "from_merchant.parquet", ["order_id", "merchant_id"]
        ),
        "pickup_at": ParquetSink(relationships_dir / "pickup_at.parquet", ["order_id", "address_key"]),
        "dropoff_at": ParquetSink(relationships_dir / "dropoff_at.parquet", ["order_id", "address_key"]),
        "paid_by": ParquetSink(relationships_dir / "paid_by.parquet", ["order_id", "payment_method"]),
        "used_promo": ParquetSink(relationships_dir / "used_promo.parquet", ["order_id", "promotion_code"]),
        "cancelled_by": ParquetSink(relationships_dir / "cancelled_by.parquet", ["order_id", "cancel_by"]),
        "has_cancel_reason": ParquetSink(
            relationships_dir / "has_cancel_reason.parquet", ["order_id", "cancel_description"]
        ),
        "dropoff_failed_by": ParquetSink(
            relationships_dir / "dropoff_failed_by.parquet", ["order_id", "food_dropoff_fail_by"]
        ),
        "has_dropoff_fail_code": ParquetSink(
            relationships_dir / "has_dropoff_fail_code.parquet", ["order_id", "food_dropoff_fail_code"]
        ),
        "uses_service": ParquetSink(relationships_dir / "uses_service.parquet", ["order_id", "service_name"]),
        "uses_service_type": ParquetSink(relationships_dir / "uses_service_type.parquet", ["order_id", "service_type"]),
        "uses_sub_vertical": ParquetSink(
            relationships_dir / "uses_sub_vertical.parquet", ["order_id", "sub_vertical_name"]
        ),
        "uses_travel_mode": ParquetSink(
            relationships_dir / "uses_travel_mode.parquet", ["order_id", "travel_mode"]
        ),
        "uses_channel_type": ParquetSink(
            relationships_dir / "uses_channel_type.parquet", ["order_id", "channel_type"]
        ),
    }

    customers: set[str] = set()
    drivers: set[str] = set()
    merchants: set[str] = set()
    payment_methods: set[str] = set()
    promotion_codes: set[str] = set()
    promotion_campaigns: set[str] = set()
    cancel_actors: set[str] = set()
    cancel_reasons: set[str] = set()
    dropoff_fail_actors: set[str] = set()
    dropoff_fail_codes: set[str] = set()
    ride_services: set[str] = set()
    service_types: set[str] = set()
    sub_verticals: set[str] = set()
    travel_modes: set[str] = set()
    channel_types: set[str] = set()
    promo_campaign_pairs: set[tuple[str, str]] = set()
    addresses: dict[str, tuple[str | None, str | None, str | None, str]] = {}
    address_cache: dict[str, str] = {}
    checks: list[dict[str, object]] = []
    processed_rows = 0

    try:
        for batch_number, batch in enumerate(batches, start=1):
            frame = batch_to_frame(batch)
            processed_rows += len(frame)
            checks.extend(quality_report(frame, args.domain))

            for column in (
                "customer_id",
                "driver_id",
                "merchant_id",
                "payment_method",
                "promotion_code",
                "promotion_campaign_code",
                "food_dropoff_fail_by",
                "food_dropoff_fail_code",
                "service_type",
                "sub_vertical_name",
                "channel_type",
            ):
                if column not in frame.columns:
                    frame[column] = pd.NA

            customers.update(clean_id_values(frame["customer_id"]))
            drivers.update(clean_id_values(frame["driver_id"]))
            merchants.update(clean_id_values(frame["merchant_id"]))
            payment_methods.update(clean_id_values(frame["payment_method"]))
            promotion_codes.update(clean_id_values(frame["promotion_code"]))
            promotion_campaigns.update(clean_id_values(frame["promotion_campaign_code"]))
            cancel_actors.update(clean_id_values(frame["cancel_by"]))
            cancel_reasons.update(clean_id_values(frame["cancel_description"]))
            dropoff_fail_actors.update(clean_id_values(frame["food_dropoff_fail_by"]))
            dropoff_fail_codes.update(clean_id_values(frame["food_dropoff_fail_code"]))
            ride_services.update(clean_id_values(frame["service_name"]))
            service_types.update(clean_id_values(frame["service_type"]))
            sub_verticals.update(clean_id_values(frame["sub_vertical_name"]))
            travel_modes.update(clean_id_values(frame["travel_mode"]))
            channel_types.update(clean_id_values(frame["channel_type"]))

            pairs = frame[["promotion_code", "promotion_campaign_code"]].dropna()
            for promo, campaign in pairs.itertuples(index=False, name=None):
                promo_text = str(promo).strip()
                campaign_text = str(campaign).strip()
                if promo_text and campaign_text:
                    promo_campaign_pairs.add((promo_text, campaign_text))

            frame["pickup_address_key"] = build_address_keys(
                frame,
                "pickup_province_name",
                "pickup_district_name",
                "pickup_address",
                addresses,
                address_cache,
            )
            frame["dropoff_address_key"] = build_address_keys(
                frame,
                "last_dropoff_province_name",
                "last_dropoff_district_name",
                "last_dropoff_address",
                addresses,
                address_cache,
            )

            order_sink.write(normalize_order_frame(frame, args.domain))
            relationship_sinks["placed"].write(frame[["customer_id", "order_id"]])
            relationship_sinks["served"].write(frame[["driver_id", "order_id"]])
            relationship_sinks["from_merchant"].write(frame[["order_id", "merchant_id"]])
            relationship_sinks["pickup_at"].write(
                frame[["order_id", "pickup_address_key"]].rename(
                    columns={"pickup_address_key": "address_key"}
                )
            )
            relationship_sinks["dropoff_at"].write(
                frame[["order_id", "dropoff_address_key"]].rename(
                    columns={"dropoff_address_key": "address_key"}
                )
            )
            relationship_sinks["paid_by"].write(frame[["order_id", "payment_method"]])
            relationship_sinks["used_promo"].write(frame[["order_id", "promotion_code"]])
            relationship_sinks["cancelled_by"].write(frame[["order_id", "cancel_by"]])
            relationship_sinks["has_cancel_reason"].write(frame[["order_id", "cancel_description"]])
            relationship_sinks["dropoff_failed_by"].write(frame[["order_id", "food_dropoff_fail_by"]])
            relationship_sinks["has_dropoff_fail_code"].write(frame[["order_id", "food_dropoff_fail_code"]])
            relationship_sinks["uses_service"].write(frame[["order_id", "service_name"]])
            relationship_sinks["uses_service_type"].write(frame[["order_id", "service_type"]])
            relationship_sinks["uses_sub_vertical"].write(frame[["order_id", "sub_vertical_name"]])
            relationship_sinks["uses_travel_mode"].write(frame[["order_id", "travel_mode"]])
            relationship_sinks["uses_channel_type"].write(frame[["order_id", "channel_type"]])

            print(
                f"batch={batch_number} rows={processed_rows:,} "
                f"customers={len(customers):,} merchants={len(merchants):,} "
                f"addresses={len(addresses):,}",
                flush=True,
            )
    finally:
        order_sink.close()
        for sink in relationship_sinks.values():
            sink.close()

    if processed_rows != expected_rows:
        raise RuntimeError(f"Processed {processed_rows} rows; expected {expected_rows}")

    node_counts = {
        "Order": order_sink.rows,
        "Customer": write_node_file(nodes_dir / "customers.parquet", {"customer_id": sorted(customers)}),
        "Driver": write_node_file(nodes_dir / "drivers.parquet", {"driver_id": sorted(drivers)}),
        "Merchant": write_node_file(nodes_dir / "merchants.parquet", {"merchant_id": sorted(merchants)}),
        "PaymentMethod": write_node_file(
            nodes_dir / "payment_methods.parquet", {"name": sorted(payment_methods)}
        ),
        "PromotionCode": write_node_file(
            nodes_dir / "promotion_codes.parquet", {"code": sorted(promotion_codes)}
        ),
        "PromotionCampaign": write_node_file(
            nodes_dir / "promotion_campaigns.parquet", {"code": sorted(promotion_campaigns)}
        ),
        "CancelActor": write_node_file(nodes_dir / "cancel_actors.parquet", {"name": sorted(cancel_actors)}),
        "CancelReason": write_node_file(nodes_dir / "cancel_reasons.parquet", {"reason": sorted(cancel_reasons)}),
        "DropoffFailActor": write_node_file(
            nodes_dir / "dropoff_fail_actors.parquet", {"name": sorted(dropoff_fail_actors)}
        ),
        "DropoffFailCode": write_node_file(
            nodes_dir / "dropoff_fail_codes.parquet", {"code": sorted(dropoff_fail_codes)}
        ),
        "RideService": write_node_file(nodes_dir / "ride_services.parquet", {"name": sorted(ride_services)}),
        "ServiceType": write_node_file(nodes_dir / "service_types.parquet", {"name": sorted(service_types)}),
        "SubVertical": write_node_file(nodes_dir / "sub_verticals.parquet", {"name": sorted(sub_verticals)}),
        "TravelMode": write_node_file(nodes_dir / "travel_modes.parquet", {"name": sorted(travel_modes)}),
        "ChannelType": write_node_file(nodes_dir / "channel_types.parquet", {"name": sorted(channel_types)}),
    }

    address_rows = sorted(addresses.items())
    node_counts["Address"] = write_node_file(
        nodes_dir / "addresses.parquet",
        {
            "address_key": [item[0] for item in address_rows],
            "address": [item[1][0] for item in address_rows],
            "district": [item[1][1] for item in address_rows],
            "province": [item[1][2] for item in address_rows],
        },
    )

    relationship_counts = {
        name: sink.rows for name, sink in relationship_sinks.items()
    }
    sorted_pairs = sorted(promo_campaign_pairs)
    relationship_counts["in_campaign"] = write_node_file(
        relationships_dir / "in_campaign.parquet",
        {
            "promotion_code": [pair[0] for pair in sorted_pairs],
            "promotion_campaign_code": [pair[1] for pair in sorted_pairs],
        },
    )

    quality = pd.DataFrame(checks)
    quality_summary = quality.groupby(["domain", "check_name"], as_index=False).agg(
        failed_rows=("failed_rows", "sum")
    )
    quality_summary.to_csv(output / "quality_report.csv", index=False)

    manifest = {
        "source": str(source) if source is not None else args.sql_uri,
        "source_kind": "sql" if args.sql_uri else "file",
        "domain": args.domain,
        "rows": processed_rows,
        "node_counts": node_counts,
        "relationship_counts": relationship_counts,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"Order nodes: {node_counts['Order']:,}")
    for label, count in node_counts.items():
        if label != "Order":
            print(f"{label} nodes: {count:,}")
    for relationship, count in relationship_counts.items():
        print(f"{relationship} relationships: {count:,}")
    print(f"Prepared import files in {output}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)





