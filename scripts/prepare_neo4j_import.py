"""Prepare deduplicated Parquet node and relationship files for neo4j-admin."""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import shutil
import sys
import unicodedata
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


ENTITY_COLUMNS = [
    "order_id",
    "customer_id",
    "driver_id",
    "pickup_province_name",
    "pickup_district_name",
    "pickup_address",
    "last_dropoff_province_name",
    "last_dropoff_district_name",
    "last_dropoff_address",
    "payment_method",
    "promotion_code",
    "promotion_campaign_code",
]

ORDER_HEADER = [
    ("order_id:ID(Order-ID)", "order_id"),
    ("status:string", "order_status"),
    ("cancel_by:string", "cancel_by"),
    ("cancel_description:string", "cancel_description"),
    ("order_time:localdatetime", "order_time_local_tz"),
    ("pickup_completed_at:localdatetime", "pickup_completed_at_local_tz"),
    ("completed_at:localdatetime", "complete_time_local_tz"),
    ("service_type:string", "service_type"),
    ("service_name:string", "service_name"),
    ("sub_vertical_name:string", "sub_vertical_name"),
    ("travel_mode:string", "travel_mode"),
    ("channel_type:string", "channel_type"),
    ("is_now_order:boolean", "is_now_order"),
    ("is_schedule_order:boolean", "is_schedule_order"),
    ("is_roundtrip:boolean", "is_roundtrip"),
    ("declared_km:double", "declared_km"),
    ("actual_km:double", "actual_km"),
    ("km_ratio:double", "km_ratio"),
    ("intrip_time_second:long", "intrip_time_second"),
    ("avg_kmh:double", "avg_kmh"),
    ("gmv:double", "gmv"),
    ("commission:double", "commission"),
    ("net_income:double", "net_income"),
    ("discount:double", "discount"),
    ("rate_by_customer:long", "rate_by_customer"),
    ("rate_by_driver:long", "rate_by_driver"),
]

HEADERS: dict[str, list[tuple[str, str]]] = {
    "orders": ORDER_HEADER,
    "customers": [("customer_id:ID(Customer-ID)", "customer_id")],
    "drivers": [("driver_id:ID(Driver-ID)", "driver_id")],
    "addresses": [
        ("address_key:ID(Address-ID)", "address_key"),
        ("address:string", "address"),
        ("district:string", "district"),
        ("province:string", "province"),
    ],
    "payment_methods": [("name:ID(Payment-ID)", "name")],
    "promotion_codes": [("code:ID(Promotion-ID)", "code")],
    "promotion_campaigns": [("code:ID(Campaign-ID)", "code")],
    "placed": [
        (":START_ID(Customer-ID)", "customer_id"),
        (":END_ID(Order-ID)", "order_id"),
    ],
    "served": [
        (":START_ID(Driver-ID)", "driver_id"),
        (":END_ID(Order-ID)", "order_id"),
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
}


class ParquetSink:
    def __init__(self, path: Path, columns: list[str]) -> None:
        self.path = path
        self.columns = columns
        self.writer: pq.ParquetWriter | None = None
        self.rows = 0

    def write(self, frame: pd.DataFrame) -> None:
        clean = frame[self.columns].dropna().copy()
        if clean.empty:
            return
        for column in self.columns:
            clean[column] = clean[column].astype(str)
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
        default=Path("data/orders_ride_masked_2026-07-14.parquet"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/neo4j-import"),
    )
    parser.add_argument("--batch-size", type=int, default=100_000)
    parser.add_argument("--minimum-free-gb", type=float, default=12.0)
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
        frame[province_column],
        frame[district_column],
        frame[address_column],
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


def string_values(series: pd.Series) -> set[str]:
    return {str(value) for value in series.dropna().unique()}


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
    marker = output / ".vsf-graph-import"
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


def main() -> int:
    args = parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)

    output.mkdir(parents=True, exist_ok=True)
    free_gb = shutil.disk_usage(output).free / (1024**3)
    if free_gb < args.minimum_free_gb:
        raise RuntimeError(
            f"Only {free_gb:.1f} GB free on {output.drive}; "
            f"at least {args.minimum_free_gb:.1f} GB is required"
        )

    parquet_file = pq.ParquetFile(source)
    if parquet_file.metadata.num_rows == 0:
        raise RuntimeError("Source parquet is empty")

    nodes_dir, relationships_dir = prepare_directories(output, args.overwrite)
    sinks = {
        "placed": ParquetSink(
            relationships_dir / "placed.parquet", ["customer_id", "order_id"]
        ),
        "served": ParquetSink(
            relationships_dir / "served.parquet", ["driver_id", "order_id"]
        ),
        "pickup_at": ParquetSink(
            relationships_dir / "pickup_at.parquet", ["order_id", "address_key"]
        ),
        "dropoff_at": ParquetSink(
            relationships_dir / "dropoff_at.parquet", ["order_id", "address_key"]
        ),
        "paid_by": ParquetSink(
            relationships_dir / "paid_by.parquet", ["order_id", "payment_method"]
        ),
        "used_promo": ParquetSink(
            relationships_dir / "used_promo.parquet", ["order_id", "promotion_code"]
        ),
    }

    customers: set[str] = set()
    drivers: set[str] = set()
    payment_methods: set[str] = set()
    promotion_codes: set[str] = set()
    promotion_campaigns: set[str] = set()
    promo_campaign_pairs: set[tuple[str, str]] = set()
    addresses: dict[str, tuple[str | None, str | None, str | None, str]] = {}
    address_cache: dict[str, str] = {}
    processed_rows = 0

    try:
        batches = parquet_file.iter_batches(
            batch_size=args.batch_size,
            columns=ENTITY_COLUMNS,
            use_threads=True,
        )
        for batch_number, batch in enumerate(batches, start=1):
            frame = batch.to_pandas()
            processed_rows += len(frame)

            customers.update(string_values(frame["customer_id"]))
            drivers.update(string_values(frame["driver_id"]))
            payment_methods.update(string_values(frame["payment_method"]))
            promotion_codes.update(string_values(frame["promotion_code"]))
            promotion_campaigns.update(
                string_values(frame["promotion_campaign_code"])
            )

            pairs = frame[["promotion_code", "promotion_campaign_code"]].dropna()
            promo_campaign_pairs.update(
                (str(promo), str(campaign))
                for promo, campaign in pairs.itertuples(index=False, name=None)
            )

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

            sinks["placed"].write(frame[["customer_id", "order_id"]])
            sinks["served"].write(frame[["driver_id", "order_id"]])
            sinks["pickup_at"].write(
                frame[["order_id", "pickup_address_key"]].rename(
                    columns={"pickup_address_key": "address_key"}
                )
            )
            sinks["dropoff_at"].write(
                frame[["order_id", "dropoff_address_key"]].rename(
                    columns={"dropoff_address_key": "address_key"}
                )
            )
            sinks["paid_by"].write(frame[["order_id", "payment_method"]])
            sinks["used_promo"].write(frame[["order_id", "promotion_code"]])
            print(
                f"batch={batch_number} rows={processed_rows:,} "
                f"customers={len(customers):,} addresses={len(addresses):,}",
                flush=True,
            )
    finally:
        for sink in sinks.values():
            sink.close()

    expected_rows = parquet_file.metadata.num_rows
    if processed_rows != expected_rows:
        raise RuntimeError(f"Processed {processed_rows} rows; expected {expected_rows}")

    node_counts = {
        "Customer": write_node_file(
            nodes_dir / "customers.parquet",
            {"customer_id": sorted(customers)},
        ),
        "Driver": write_node_file(
            nodes_dir / "drivers.parquet",
            {"driver_id": sorted(drivers)},
        ),
        "PaymentMethod": write_node_file(
            nodes_dir / "payment_methods.parquet",
            {"name": sorted(payment_methods)},
        ),
        "PromotionCode": write_node_file(
            nodes_dir / "promotion_codes.parquet",
            {"code": sorted(promotion_codes)},
        ),
        "PromotionCampaign": write_node_file(
            nodes_dir / "promotion_campaigns.parquet",
            {"code": sorted(promotion_campaigns)},
        ),
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

    sorted_pairs = sorted(promo_campaign_pairs)
    relationship_counts = {name: sink.rows for name, sink in sinks.items()}
    relationship_counts["in_campaign"] = write_node_file(
        relationships_dir / "in_campaign.parquet",
        {
            "promotion_code": [pair[0] for pair in sorted_pairs],
            "promotion_campaign_code": [pair[1] for pair in sorted_pairs],
        },
    )

    print(f"Order nodes: {expected_rows:,}")
    for label, count in node_counts.items():
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

