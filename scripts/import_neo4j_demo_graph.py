"""Import a compact base handoff graph into Neo4j directly from cleaned ride orders."""

from __future__ import annotations

import argparse
import glob
import sys
import time
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd
import pyarrow.parquet as pq

from src.config.settings import settings

if TYPE_CHECKING:
    from neo4j import Driver


BASE_COLUMNS = [
    "order_id",
    "driver_id",
    "customer_id",
    "order_date",
]

UPSERT_BASE_BATCH_CYPHER = """
UNWIND $rows AS row
MERGE (o:Order {order_id: row.order_id})
SET o.order_date = row.order_date,
    o.domain = 'ride',
    o.demo_scope = true
MERGE (d:Driver {driver_id: row.driver_id})
SET d.demo_scope = true
MERGE (c:Customer {customer_id: row.customer_id})
SET c.demo_scope = true
MERGE (d)-[:SERVED]->(o)
MERGE (c)-[:PLACED]->(o)
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import a compact base handoff graph into Neo4j directly from cleaned ride orders."
    )
    parser.add_argument(
        "--orders-input",
        default="data/handoff/ride/cleaned_orders/orders_ride_masked_2026-07-2[4-9].parquet",
        help="Path, directory, or glob pattern for cleaned ride orders.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=2_000,
        help="Neo4j write batch size.",
    )
    parser.add_argument(
        "--cypher",
        default="src/graph/cypher/002_demo_visualization_constraints.cypher",
        help="Cypher file that defines demo constraints and indexes.",
    )
    parser.add_argument(
        "--wait-seconds",
        type=int,
        default=180,
        help="Seconds to wait for Neo4j to become reachable.",
    )
    parser.add_argument(
        "--wipe-existing",
        action="store_true",
        help="Delete all existing nodes and relationships in the target database before import.",
    )
    parser.add_argument(
        "--confirm-wipe",
        default="",
        help="Safety phrase required with --wipe-existing. Must equal DELETE_ALL_DATA.",
    )
    parser.add_argument(
        "--max-orders",
        type=int,
        default=0,
        help="Optional cap on the number of imported orders; 0 disables the cap.",
    )
    return parser.parse_args()


def split_cypher(script: str) -> list[str]:
    return [statement.strip() for statement in script.split(";") if statement.strip()]


def _resolve_input_paths(raw_path: str) -> list[Path]:
    if any(char in raw_path for char in "*?[]"):
        return [Path(match) for match in sorted(glob.glob(raw_path))]
    path = Path(raw_path)
    if path.is_dir():
        return sorted(candidate for candidate in path.glob("*.parquet") if candidate.is_file())
    return [path]


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


def ensure_constraints(driver: Driver, cypher_path: Path) -> None:
    for statement in split_cypher(cypher_path.read_text(encoding="utf-8")):
        driver.execute_query(statement, database_=settings.neo4j_database)


def wipe_existing_graph(driver: Driver) -> None:
    driver.execute_query(
        "MATCH (n) DETACH DELETE n",
        database_=settings.neo4j_database,
    )


def source_batches(paths: list[Path], batch_size: int):
    total_rows = 0
    resolved_paths: list[tuple[Path, pq.ParquetFile]] = []
    for path in paths:
        if path.suffix.lower() != ".parquet":
            raise ValueError(f"Unsupported orders input format: {path.suffix}")
        parquet_file = pq.ParquetFile(path)
        total_rows += parquet_file.metadata.num_rows
        resolved_paths.append((path, parquet_file))

    def _iter_batches():
        for path, parquet_file in resolved_paths:
            available_columns = set(pq.read_schema(path).names)
            selected_columns = [column for column in BASE_COLUMNS if column in available_columns]
            for batch in parquet_file.iter_batches(
                batch_size=batch_size,
                columns=selected_columns,
                use_threads=True,
            ):
                frame = batch.to_pandas()
                for column in BASE_COLUMNS:
                    if column not in frame.columns:
                        frame[column] = pd.NA
                yield frame[BASE_COLUMNS]

    return total_rows, _iter_batches()


def optional_string(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def optional_date(value: object) -> date | None:
    if value is None or pd.isna(value):
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date()


def normalize_base_frame(frame: pd.DataFrame) -> pd.DataFrame:
    working = frame.copy()
    for column in BASE_COLUMNS:
        if column not in working.columns:
            working.loc[:, column] = pd.NA
    for column in ("order_id", "driver_id", "customer_id"):
        working.loc[:, column] = working[column].astype("string").str.strip()
    working = working[
        working["order_id"].notna()
        & working["order_id"].ne("")
        & working["driver_id"].notna()
        & working["driver_id"].ne("")
        & working["customer_id"].notna()
        & working["customer_id"].ne("")
    ].copy()
    working = working.drop_duplicates(subset=["order_id"], keep="first").reset_index(drop=True)
    return working


def prepare_rows(frame: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        order_id = optional_string(row.get("order_id"))
        driver_id = optional_string(row.get("driver_id"))
        customer_id = optional_string(row.get("customer_id"))
        if not order_id or not driver_id or not customer_id:
            continue
        rows.append(
            {
                "order_id": order_id,
                "driver_id": driver_id,
                "customer_id": customer_id,
                "order_date": optional_date(row.get("order_date")),
            }
        )
    return rows


def import_batches(driver: Driver, orders_input: str, batch_size: int, max_orders: int) -> dict[str, int]:
    input_paths = _resolve_input_paths(orders_input)
    if not input_paths:
        raise FileNotFoundError(f"No order inputs matched: {orders_input}")

    expected_rows, batches = source_batches(input_paths, batch_size)
    if expected_rows <= 0:
        raise RuntimeError("Orders input data is empty")

    counters = {
        "source_rows": expected_rows,
        "processed_rows": 0,
        "valid_rows": 0,
    }
    imported_rows = 0

    for batch_number, raw_frame in enumerate(batches, start=1):
        counters["processed_rows"] += len(raw_frame)
        frame = normalize_base_frame(raw_frame)
        if max_orders > 0:
            remaining = max_orders - imported_rows
            if remaining <= 0:
                break
            frame = frame.head(remaining).copy()
        rows = prepare_rows(frame)
        if not rows:
            continue
        driver.execute_query(
            UPSERT_BASE_BATCH_CYPHER,
            rows=rows,
            database_=settings.neo4j_database,
        )
        counters["valid_rows"] += len(rows)
        imported_rows += len(rows)
        print(
            f"batch={batch_number} processed={counters['processed_rows']:,} valid_rows={counters['valid_rows']:,}",
            flush=True,
        )

    return counters


def main() -> int:
    args = parse_args()
    cypher_path = Path(args.cypher).resolve()
    if not cypher_path.is_file():
        raise FileNotFoundError(cypher_path)

    if args.wipe_existing and args.confirm_wipe != "DELETE_ALL_DATA":
        raise ValueError("Pass --confirm-wipe DELETE_ALL_DATA together with --wipe-existing")

    driver = wait_for_driver(args.wait_seconds)
    try:
        if args.wipe_existing:
            wipe_existing_graph(driver)
        ensure_constraints(driver, cypher_path)
        counters = import_batches(driver, args.orders_input, args.batch_size, args.max_orders)
    finally:
        driver.close()

    print(f"Source rows: {counters['source_rows']:,}")
    print(f"Valid imported rows: {counters['valid_rows']:,}")
    print("Neo4j base demo graph import completed")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
