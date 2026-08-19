"""Build a compact base handoff dataset for Neo4j demo visualization."""

from __future__ import annotations

import argparse
import glob
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq


BASE_COLUMNS = [
    "order_id",
    "driver_id",
    "customer_id",
    "order_date",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a compact base handoff dataset for Neo4j demo visualization."
    )
    parser.add_argument(
        "--orders-input",
        default="data/handoff/ride/cleaned_orders/orders_ride_masked_2026-07-2[4-9].parquet",
        help="Path, directory, or glob pattern for cleaned ride orders.",
    )
    parser.add_argument(
        "--output",
        default="reports/task3/neo4j_demo_base_orders.parquet",
        help="Where the compact base handoff dataset should be written.",
    )
    parser.add_argument(
        "--max-orders",
        type=int,
        default=0,
        help="Optional cap on the number of orders written; 0 disables the cap.",
    )
    return parser.parse_args()


def _resolve_input_paths(raw_path: str) -> list[Path]:
    if any(char in raw_path for char in "*?[]"):
        return [Path(match) for match in sorted(glob.glob(raw_path))]
    path = Path(raw_path)
    if path.is_dir():
        return sorted(candidate for candidate in path.glob("*.parquet") if candidate.is_file())
    return [path]


def _iter_order_frames(paths: list[Path], batch_size: int = 250_000):
    for input_path in paths:
        if input_path.suffix.lower() != ".parquet":
            raise ValueError(f"Unsupported orders input format: {input_path.suffix}")
        available_columns = set(pq.read_schema(input_path).names)
        selected_columns = [column for column in BASE_COLUMNS if column in available_columns]
        parquet_file = pq.ParquetFile(input_path)
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


def _normalize_orders(frame: pd.DataFrame) -> pd.DataFrame:
    working = frame.copy()
    working["order_id"] = working["order_id"].astype("string").str.strip()
    working["driver_id"] = working["driver_id"].astype("string").str.strip()
    working["customer_id"] = working["customer_id"].astype("string").str.strip()
    working = working[
        working["order_id"].notna()
        & working["order_id"].ne("")
        & working["driver_id"].notna()
        & working["driver_id"].ne("")
        & working["customer_id"].notna()
        & working["customer_id"].ne("")
    ].copy()
    working["order_date"] = pd.to_datetime(working["order_date"], errors="coerce").dt.date
    return working.drop_duplicates(subset=["order_id"], keep="first").reset_index(drop=True)


def build_demo_base_dataset(
    *,
    orders_input: str,
    output_path: Path,
    max_orders: int,
) -> pd.DataFrame:
    order_paths = _resolve_input_paths(orders_input)
    if not order_paths:
        raise FileNotFoundError(f"No order inputs matched: {orders_input}")

    kept_frames: list[pd.DataFrame] = []
    for raw_frame in _iter_order_frames(order_paths):
        orders = _normalize_orders(raw_frame)
        if not orders.empty:
            kept_frames.append(orders)

    if not kept_frames:
        raise RuntimeError("No valid orders found in the selected handoff input")

    demo_orders = pd.concat(kept_frames, ignore_index=True)
    demo_orders = demo_orders.drop_duplicates(subset=["order_id"], keep="first").reset_index(drop=True)
    demo_orders = demo_orders.sort_values(["order_date", "order_id"], ascending=[False, True]).reset_index(drop=True)

    if max_orders > 0:
        demo_orders = demo_orders.head(max_orders).copy()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    demo_orders.to_parquet(output_path, index=False)
    return demo_orders


def main() -> None:
    args = parse_args()
    demo_orders = build_demo_base_dataset(
        orders_input=args.orders_input,
        output_path=Path(args.output),
        max_orders=args.max_orders,
    )

    print(f"Base demo orders written: {len(demo_orders):,}")
    print(f"Drivers in base demo: {demo_orders['driver_id'].nunique():,}")
    print(f"Customers in base demo: {demo_orders['customer_id'].nunique():,}")
    print(f"Output: {Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
