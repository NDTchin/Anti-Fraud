"""Update demo flag properties in Neo4j from flagged report output."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd
import pyarrow.parquet as pq

from src.config.settings import settings

if TYPE_CHECKING:
    from neo4j import Driver


FLAGGED_COLUMNS = [
    "order_id",
    "driver_id",
    "customer_id",
    "priority_score",
    "risk_tier",
]

RESET_ORDER_FLAGS_CYPHER = """
MATCH (o:Order)
WHERE coalesce(o.demo_scope, false) = true
WITH o LIMIT $limit
SET o.is_flagged = false,
    o.priority_score = null,
    o.risk_tier = null
RETURN count(o) AS updated
"""

RESET_DRIVER_FLAGS_CYPHER = """
MATCH (d:Driver)
WHERE coalesce(d.demo_scope, false) = true
WITH d LIMIT $limit
SET d.is_flagged = false,
    d.flagged_order_count = 0,
    d.flag_refresh_done = false
RETURN count(d) AS updated
"""

RESET_CUSTOMER_FLAGS_CYPHER = """
MATCH (c:Customer)
WHERE coalesce(c.demo_scope, false) = true
WITH c LIMIT $limit
SET c.is_flagged = false,
    c.flagged_order_count = 0,
    c.flag_refresh_done = false
RETURN count(c) AS updated
"""

UPSERT_FLAG_BATCH_CYPHER = """
UNWIND $rows AS row
MATCH (o:Order {order_id: row.order_id})
WHERE coalesce(o.demo_scope, false) = true
SET o.is_flagged = true,
    o.priority_score = row.priority_score,
    o.risk_tier = row.risk_tier
"""

REFRESH_DRIVER_FLAGS_CYPHER = """
MATCH (d:Driver)
WHERE coalesce(d.demo_scope, false) = true
  AND coalesce(d.flag_refresh_done, false) = false
WITH d LIMIT $limit
OPTIONAL MATCH (d)-[:SERVED]->(o:Order {demo_scope: true, is_flagged: true})
WITH d, count(o) AS flagged_count
SET d.flagged_order_count = flagged_count,
    d.is_flagged = flagged_count > 0,
    d.flag_refresh_done = true
RETURN count(d) AS updated
"""

REFRESH_CUSTOMER_FLAGS_CYPHER = """
MATCH (c:Customer)
WHERE coalesce(c.demo_scope, false) = true
  AND coalesce(c.flag_refresh_done, false) = false
WITH c LIMIT $limit
OPTIONAL MATCH (c)-[:PLACED]->(o:Order {demo_scope: true, is_flagged: true})
WITH c, count(o) AS flagged_count
SET c.flagged_order_count = flagged_count,
    c.is_flagged = flagged_count > 0,
    c.flag_refresh_done = true
RETURN count(c) AS updated
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update demo flag properties in Neo4j from flagged report output."
    )
    parser.add_argument(
        "--source",
        default="reports/task3/flagged_orders.parquet",
        help="Flagged-orders parquet produced by build_task3_daily_outputs.py.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=200,
        help="Neo4j write batch size.",
    )
    parser.add_argument(
        "--wait-seconds",
        type=int,
        default=180,
        help="Seconds to wait for Neo4j to become reachable.",
    )
    parser.add_argument(
        "--top-flagged-orders",
        type=int,
        default=0,
        help="Optional cap on flagged orders by priority_score; 0 disables the cap.",
    )
    parser.add_argument(
        "--skip-reset",
        action="store_true",
        help="Skip clearing old flag properties before applying the new flagged report.",
    )
    return parser.parse_args()


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


def source_batches(path: Path, batch_size: int) -> tuple[int, Any]:
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        parquet_file = pq.ParquetFile(path)
        return parquet_file.metadata.num_rows, parquet_file.iter_batches(
            batch_size=batch_size,
            columns=FLAGGED_COLUMNS,
            use_threads=True,
        )
    if suffix == ".csv":
        row_count = max(sum(1 for _ in path.open("r", encoding="utf-8")) - 1, 0)
        return row_count, pd.read_csv(path, chunksize=batch_size)
    raise ValueError(f"Unsupported flagged source format: {path.suffix}")


def batch_to_frame(batch: Any) -> pd.DataFrame:
    if hasattr(batch, "to_pandas"):
        return batch.to_pandas()
    return batch


def optional_string(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def optional_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), 2)


def normalize_flagged_frame(frame: pd.DataFrame) -> pd.DataFrame:
    working = frame.copy()
    for column in FLAGGED_COLUMNS:
        if column not in working.columns:
            working.loc[:, column] = pd.NA
    for column in ("order_id", "driver_id", "customer_id", "risk_tier"):
        working.loc[:, column] = working[column].astype("string").str.strip()
    working.loc[:, "priority_score"] = pd.to_numeric(working["priority_score"], errors="coerce")
    working = working[working["order_id"].notna() & working["order_id"].ne("")].copy()
    working = working.sort_values(["priority_score", "order_id"], ascending=[False, True])
    working = working.drop_duplicates(subset=["order_id"], keep="first").reset_index(drop=True)
    return working


def prepare_rows(frame: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        order_id = optional_string(row.get("order_id"))
        if not order_id:
            continue
        rows.append(
            {
                "order_id": order_id,
                "priority_score": optional_float(row.get("priority_score")),
                "risk_tier": optional_string(row.get("risk_tier")),
            }
        )
    return rows


def reset_flags(driver: Driver) -> None:
    _run_batched_reset(driver, RESET_ORDER_FLAGS_CYPHER, "orders")
    _run_batched_reset(driver, RESET_DRIVER_FLAGS_CYPHER, "drivers")
    _run_batched_reset(driver, RESET_CUSTOMER_FLAGS_CYPHER, "customers")


def _run_batched_reset(driver: Driver, query: str, label: str, limit: int = 5_000) -> None:
    while True:
        with driver.session(database=settings.neo4j_database) as session:
            record = session.run(query, limit=limit).single()
        updated = int(record["updated"]) if record else 0
        if updated <= 0:
            break
        print(f"reset_{label}={updated:,}", flush=True)


def apply_flag_batches(
    driver: Driver,
    source: Path,
    batch_size: int,
    top_flagged_orders: int,
) -> dict[str, int]:
    expected_rows, batches = source_batches(source, batch_size)
    if expected_rows <= 0:
        raise RuntimeError("Flagged report data is empty")

    counters = {
        "source_rows": expected_rows,
        "processed_rows": 0,
        "valid_rows": 0,
    }
    applied_rows = 0

    for batch_number, batch in enumerate(batches, start=1):
        raw_frame = batch_to_frame(batch)
        counters["processed_rows"] += len(raw_frame)
        frame = normalize_flagged_frame(raw_frame)
        if top_flagged_orders > 0:
            remaining = top_flagged_orders - applied_rows
            if remaining <= 0:
                break
            frame = frame.head(remaining).copy()
        rows = prepare_rows(frame)
        if not rows:
            continue
        with driver.session(database=settings.neo4j_database) as session:
            session.run(UPSERT_FLAG_BATCH_CYPHER, rows=rows).consume()
        counters["valid_rows"] += len(rows)
        applied_rows += len(rows)
        print(
            f"batch={batch_number} processed={counters['processed_rows']:,} valid_rows={counters['valid_rows']:,}",
            flush=True,
        )

    return counters


def refresh_actor_flags(driver: Driver) -> None:
    _run_batched_refresh(driver, REFRESH_DRIVER_FLAGS_CYPHER, "drivers")
    _run_batched_refresh(driver, REFRESH_CUSTOMER_FLAGS_CYPHER, "customers")


def _run_batched_refresh(driver: Driver, query: str, label: str, limit: int = 1_000) -> None:
    while True:
        with driver.session(database=settings.neo4j_database) as session:
            record = session.run(query, limit=limit).single()
        updated = int(record["updated"]) if record else 0
        if updated <= 0:
            break
        print(f"refresh_{label}={updated:,}", flush=True)


def main() -> int:
    args = parse_args()
    source = Path(args.source).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)

    driver = wait_for_driver(args.wait_seconds)
    try:
        if not args.skip_reset:
            reset_flags(driver)
        counters = apply_flag_batches(driver, source, args.batch_size, args.top_flagged_orders)
        refresh_actor_flags(driver)
    finally:
        driver.close()

    print(f"Source rows: {counters['source_rows']:,}")
    print(f"Valid flagged rows applied: {counters['valid_rows']:,}")
    print("Neo4j demo flags update completed")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
