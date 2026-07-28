from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class RideCollusionGraphConfig:
    extreme_trip_quantile: float = 0.9999

    def validate(self) -> None:
        if not 0 < self.extreme_trip_quantile < 1:
            raise ValueError("extreme_trip_quantile must be between 0 and 1.")


def ensure_datetime(series: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(series):
        return pd.to_datetime(series, errors="coerce")
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_datetime(series, unit="s", errors="coerce")
    return pd.to_datetime(series, errors="coerce")


def load_ride_orders(path: str | Path) -> pd.DataFrame:
    columns = [
        "order_id",
        "driver_id",
        "customer_id",
        "order_status",
        "order_time_local_tz",
        "pickup_completed_at_local_tz",
        "complete_time_local_tz",
        "service_name",
        "pickup_province_name",
        "pickup_district_name",
        "pickup_address",
        "last_dropoff_province_name",
        "last_dropoff_district_name",
        "last_dropoff_address",
        "avg_kmh",
        "gmv",
        "discount",
        "promotion_code",
        "payment_method",
        "source_file_date",
        "order_date",
        "is_cancelled",
    ]
    frame = pd.read_parquet(path, columns=columns).copy()
    return frame.assign(
        order_time_local_tz=ensure_datetime(frame["order_time_local_tz"]),
        pickup_completed_at_local_tz=ensure_datetime(frame["pickup_completed_at_local_tz"]),
        complete_time_local_tz=ensure_datetime(frame["complete_time_local_tz"]),
        order_date=pd.to_datetime(frame["order_date"], errors="coerce").dt.date,
    )


def prepare_active_orders(frame: pd.DataFrame) -> pd.DataFrame:
    active = frame[
        frame["driver_id"].notna()
        & frame["customer_id"].notna()
        & frame["order_time_local_tz"].notna()
        & frame["is_cancelled"].fillna(0).eq(0)
    ].copy()
    active = active.assign(
        avg_kmh=pd.to_numeric(active["avg_kmh"], errors="coerce"),
        gmv=pd.to_numeric(active["gmv"], errors="coerce"),
        discount=pd.to_numeric(active["discount"], errors="coerce").fillna(0.0),
    )
    return active.assign(
        is_ghost=active["avg_kmh"].fillna(np.nan).eq(0),
        route_key=active["pickup_address"].fillna("") + " -> " + active["last_dropoff_address"].fillna(""),
    )


def build_pair_stats(
    active_orders: pd.DataFrame,
    config: RideCollusionGraphConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, float]:
    config.validate()
    pair_counts = (
        active_orders.groupby(["driver_id", "customer_id"], dropna=False)
        .size()
        .rename("n_trips")
        .reset_index()
    )
    trip_threshold = float(pair_counts["n_trips"].quantile(config.extreme_trip_quantile))

    driver_counts = active_orders.groupby("driver_id").size().rename("driver_trip_count")
    customer_counts = active_orders.groupby("customer_id").size().rename("customer_trip_count")

    candidate_pairs = pair_counts[pair_counts["n_trips"] > trip_threshold].copy()
    candidate_orders = active_orders.merge(
        candidate_pairs[["driver_id", "customer_id"]],
        on=["driver_id", "customer_id"],
        how="inner",
    )
    candidate_orders = candidate_orders.sort_values(["driver_id", "customer_id", "order_time_local_tz"]).copy()
    candidate_orders = candidate_orders.assign(
        gap_min=(
            candidate_orders.groupby(["driver_id", "customer_id"], dropna=False)["order_time_local_tz"]
            .diff()
            .dt.total_seconds()
            .div(60.0)
        )
    )

    pair_stats = (
        candidate_orders.groupby(["driver_id", "customer_id"], dropna=False)
        .agg(
            n_trips=("order_id", "nunique"),
            n_ghost=("is_ghost", "sum"),
            min_gap_min=("gap_min", "min"),
            avg_gmv=("gmv", "mean"),
            total_gmv=("gmv", "sum"),
            total_discount=("discount", "sum"),
            active_days=("order_date", "nunique"),
            latest_order_date=("order_date", "max"),
            top_service_name=("service_name", lambda values: values.mode().iat[0] if not values.mode().empty else values.iloc[0]),
            top_pickup_province_name=("pickup_province_name", lambda values: values.mode().iat[0] if not values.mode().empty else values.iloc[0]),
            top_dropoff_province_name=("last_dropoff_province_name", lambda values: values.mode().iat[0] if not values.mode().empty else values.iloc[0]),
        )
        .reset_index()
    )
    pair_stats = pair_stats.assign(ghost_rate=pair_stats["n_ghost"] / pair_stats["n_trips"])
    pair_stats = pair_stats.merge(driver_counts.rename_axis("driver_id").reset_index(), on="driver_id", how="left")
    pair_stats = pair_stats.merge(customer_counts.rename_axis("customer_id").reset_index(), on="customer_id", how="left")
    pair_stats = pair_stats.assign(
        pair_share_driver=pair_stats["n_trips"] / pair_stats["driver_trip_count"],
        pair_share_customer=pair_stats["n_trips"] / pair_stats["customer_trip_count"],
    )

    route_counts = (
        candidate_orders.groupby(["driver_id", "customer_id", "route_key"], dropna=False)
        .size()
        .rename("route_trip_count")
        .reset_index()
        .sort_values(["driver_id", "customer_id", "route_trip_count", "route_key"], ascending=[True, True, False, True])
    )
    dominant_routes = route_counts.drop_duplicates(["driver_id", "customer_id"]).rename(
        columns={"route_key": "dominant_route_key", "route_trip_count": "dominant_route_trip_count"}
    )
    pair_stats = pair_stats.merge(dominant_routes, on=["driver_id", "customer_id"], how="left")
    pair_stats = pair_stats.assign(
        dominant_route_share=pair_stats["dominant_route_trip_count"] / pair_stats["n_trips"],
        trip_threshold=trip_threshold,
    )
    return pair_stats.sort_values(["n_trips", "ghost_rate"], ascending=False), candidate_orders, trip_threshold
