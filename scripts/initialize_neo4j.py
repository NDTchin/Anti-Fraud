"""Create indexes and verify the imported graph against staged Parquet counts."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pyarrow.parquet as pq
from neo4j import Driver, GraphDatabase

from src.config.settings import settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cypher",
        type=Path,
        default=Path("src/graph/cypher/001_constraints.cypher"),
    )
    parser.add_argument(
        "--import-dir",
        type=Path,
        default=Path("data/neo4j-import"),
    )
    parser.add_argument("--wait-seconds", type=int, default=180)
    return parser.parse_args()


def wait_for_driver(wait_seconds: int) -> Driver:
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


def split_cypher(script: str) -> list[str]:
    return [statement.strip() for statement in script.split(";") if statement.strip()]


def parquet_rows(path: Path) -> int:
    return pq.ParquetFile(path).metadata.num_rows


def expected_counts(import_dir: Path) -> tuple[dict[str, int], dict[str, int]]:
    source = settings.raw_data_path
    nodes_dir = import_dir / "nodes"
    relationships_dir = import_dir / "relationships"
    orders_path = nodes_dir / "orders.parquet"
    nodes = {
        "Order": parquet_rows(orders_path) if orders_path.exists() else parquet_rows(source),
        "Customer": parquet_rows(nodes_dir / "customers.parquet"),
        "Driver": parquet_rows(nodes_dir / "drivers.parquet"),
        "Address": parquet_rows(nodes_dir / "addresses.parquet"),
        "PaymentMethod": parquet_rows(nodes_dir / "payment_methods.parquet"),
        "PromotionCode": parquet_rows(nodes_dir / "promotion_codes.parquet"),
        "PromotionCampaign": parquet_rows(
            nodes_dir / "promotion_campaigns.parquet"
        ),
    }
    optional_node_paths = {
        "Merchant": nodes_dir / "merchants.parquet",
        "CancelActor": nodes_dir / "cancel_actors.parquet",
        "CancelReason": nodes_dir / "cancel_reasons.parquet",
        "DropoffFailActor": nodes_dir / "dropoff_fail_actors.parquet",
        "DropoffFailCode": nodes_dir / "dropoff_fail_codes.parquet",
        "RideService": nodes_dir / "ride_services.parquet",
        "ServiceType": nodes_dir / "service_types.parquet",
        "SubVertical": nodes_dir / "sub_verticals.parquet",
        "TravelMode": nodes_dir / "travel_modes.parquet",
        "ChannelType": nodes_dir / "channel_types.parquet",
    }
    for label, path in optional_node_paths.items():
        if path.exists():
            nodes[label] = parquet_rows(path)
    relationships = {
        "PLACED": parquet_rows(relationships_dir / "placed.parquet"),
        "SERVED": parquet_rows(relationships_dir / "served.parquet"),
        "PICKUP_AT": parquet_rows(relationships_dir / "pickup_at.parquet"),
        "DROPOFF_AT": parquet_rows(relationships_dir / "dropoff_at.parquet"),
        "PAID_BY": parquet_rows(relationships_dir / "paid_by.parquet"),
        "USED_PROMO": parquet_rows(relationships_dir / "used_promo.parquet"),
        "IN_CAMPAIGN": parquet_rows(relationships_dir / "in_campaign.parquet"),
    }
    optional_relationship_paths = {
        "FROM_MERCHANT": relationships_dir / "from_merchant.parquet",
        "CANCELLED_BY": relationships_dir / "cancelled_by.parquet",
        "HAS_CANCEL_REASON": relationships_dir / "has_cancel_reason.parquet",
        "DROPOFF_FAILED_BY": relationships_dir / "dropoff_failed_by.parquet",
        "HAS_DROPOFF_FAIL_CODE": relationships_dir / "has_dropoff_fail_code.parquet",
        "USES_SERVICE": relationships_dir / "uses_service.parquet",
        "USES_SERVICE_TYPE": relationships_dir / "uses_service_type.parquet",
        "USES_SUB_VERTICAL": relationships_dir / "uses_sub_vertical.parquet",
        "USES_TRAVEL_MODE": relationships_dir / "uses_travel_mode.parquet",
        "USES_CHANNEL_TYPE": relationships_dir / "uses_channel_type.parquet",
    }
    for rel_type, path in optional_relationship_paths.items():
        if path.exists():
            relationships[rel_type] = parquet_rows(path)
    return nodes, relationships


def actual_counts(driver: Driver) -> tuple[dict[str, int], dict[str, int]]:
    node_records, _, _ = driver.execute_query(
        "MATCH (n) UNWIND labels(n) AS label "
        "RETURN label, count(*) AS count",
        database_=settings.neo4j_database,
    )
    relationship_records, _, _ = driver.execute_query(
        "MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS count",
        database_=settings.neo4j_database,
    )
    return (
        {record["label"]: record["count"] for record in node_records},
        {record["type"]: record["count"] for record in relationship_records},
    )


def check_counts(kind: str, expected: dict[str, int], actual: dict[str, int]) -> None:
    mismatches = []
    for name, expected_count in expected.items():
        actual_count = actual.get(name, 0)
        print(f"{kind} {name}: actual={actual_count:,} expected={expected_count:,}")
        if actual_count != expected_count:
            mismatches.append((name, expected_count, actual_count))
    if mismatches:
        raise RuntimeError(f"{kind} count mismatches: {mismatches}")


def main() -> int:
    args = parse_args()
    driver = wait_for_driver(args.wait_seconds)
    try:
        for statement in split_cypher(args.cypher.read_text(encoding="utf-8")):
            driver.execute_query(statement, database_=settings.neo4j_database)

        apoc_records, _, _ = driver.execute_query(
            "RETURN apoc.version() AS version",
            database_=settings.neo4j_database,
        )
        gds_records, _, _ = driver.execute_query(
            "RETURN gds.version() AS version",
            database_=settings.neo4j_database,
        )
        print(f"APOC version: {apoc_records[0]['version']}")
        print(f"GDS version: {gds_records[0]['version']}")

        expected_nodes, expected_relationships = expected_counts(args.import_dir)
        actual_nodes, actual_relationships = actual_counts(driver)
        check_counts("node", expected_nodes, actual_nodes)
        check_counts(
            "relationship", expected_relationships, actual_relationships
        )
    finally:
        driver.close()
    print("Neo4j graph verification passed")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)


