from __future__ import annotations

import glob
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq


COMPLETED_STATUSES = {"COMPLETED"}


@dataclass(frozen=True)
class RideCollusionGraphConfig:
    extreme_trip_quantile: float = 0.9999
    min_extreme_trip_threshold: int = 2

    def validate(self) -> None:
        if not 0 < self.extreme_trip_quantile < 1:
            raise ValueError("extreme_trip_quantile must be between 0 and 1.")
        if self.min_extreme_trip_threshold < 1:
            raise ValueError("min_extreme_trip_threshold must be at least 1.")


@dataclass(frozen=True)
class SuspiciousPairConfig:
    min_pair_trips: int = 2
    min_concentration_score: float = 0.75
    min_pair_core_score: float = 40.0

    def validate(self) -> None:
        if self.min_pair_trips < 1:
            raise ValueError("min_pair_trips must be at least 1.")
        if not 0 <= self.min_concentration_score <= 1:
            raise ValueError("min_concentration_score must be between 0 and 1.")
        if not 0 <= self.min_pair_core_score <= 100:
            raise ValueError("min_pair_core_score must be between 0 and 100.")


def ensure_datetime(series: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(series):
        return pd.to_datetime(series, errors="coerce")
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_datetime(series, unit="s", errors="coerce")
    return pd.to_datetime(series, errors="coerce")


def is_completed_status(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip().str.upper().isin(COMPLETED_STATUSES)


def _resolve_input_paths(path: str | Path) -> list[Path]:
    raw_path = str(path)
    if any(char in raw_path for char in "*?[]"):
        return [Path(match) for match in sorted(glob.glob(raw_path))]

    resolved = Path(raw_path)
    if resolved.is_dir():
        return sorted(candidate for candidate in resolved.glob("*.parquet") if candidate.is_file())
    return [resolved]


def load_ride_orders(path: str | Path) -> pd.DataFrame:
    requested_columns = [
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
        "order_date",
    ]
    input_paths = _resolve_input_paths(path)
    if not input_paths:
        raise FileNotFoundError(f"No ride input files matched: {path}")

    frames = []
    for input_path in input_paths:
        available_columns = set(pq.read_schema(input_path).names)
        selected_columns = [column for column in requested_columns if column in available_columns]
        frame = pd.read_parquet(input_path, columns=selected_columns)
        missing_columns = [column for column in requested_columns if column not in frame.columns]
        for column in missing_columns:
            frame[column] = pd.NA
        frames.append(frame[requested_columns])
    frame = pd.concat(frames, ignore_index=True).copy()
    derived_order_date = pd.to_datetime(frame["order_time_local_tz"], errors="coerce").dt.date
    if frame["order_date"].isna().all():
        frame["order_date"] = derived_order_date
    else:
        frame["order_date"] = pd.to_datetime(frame["order_date"], errors="coerce").dt.date.fillna(derived_order_date)
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
        & is_completed_status(frame["order_status"])
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


def _mode_or_first(values: pd.Series) -> object:
    cleaned = values.dropna()
    if cleaned.empty:
        return pd.NA
    mode = cleaned.mode()
    if not mode.empty:
        return mode.iloc[0]
    return cleaned.iloc[0]


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    ratio = numerator.astype(float).div(denominator.replace(0, np.nan).astype(float))
    return ratio.fillna(0.0)


def _percentile_rank(values: pd.Series) -> pd.Series:
    if values.empty:
        return pd.Series(dtype=float)
    return values.rank(method="max", pct=True).fillna(0.0)


def _build_volume_cohort(pair_stats: pd.DataFrame) -> pd.Series:
    return (
        pair_stats["top_service_name"].fillna("unknown").astype("string").str.strip().fillna("unknown")
        + "|"
        + pair_stats["top_pickup_province_name"].fillna("unknown").astype("string").str.strip().fillna("unknown")
    )


def finalize_pair_stats(
    pair_stats: pd.DataFrame,
    config: RideCollusionGraphConfig,
    trip_threshold: float,
) -> pd.DataFrame:
    if pair_stats.empty:
        return pair_stats.copy()

    finalized = pair_stats.copy()
    finalized["volume_cohort"] = _build_volume_cohort(finalized)
    cohort_thresholds = (
        finalized.groupby("volume_cohort", dropna=False)["n_trips"]
        .quantile(config.extreme_trip_quantile)
        .rename("cohort_trip_threshold")
        .reset_index()
    )
    cohort_thresholds["cohort_trip_threshold"] = cohort_thresholds["cohort_trip_threshold"].map(
        lambda value: float(max(config.min_extreme_trip_threshold, value))
    )
    finalized = finalized.merge(cohort_thresholds, on="volume_cohort", how="left")
    finalized["trip_count_percentile"] = (
        finalized.groupby("volume_cohort", dropna=False)["n_trips"].transform(_percentile_rank).round(4)
    )

    driver_unique_customers = finalized.groupby("driver_id", dropna=False)["customer_id"].transform("nunique").clip(lower=1)
    customer_unique_drivers = finalized.groupby("customer_id", dropna=False)["driver_id"].transform("nunique").clip(lower=1)
    finalized["expected_share_driver"] = (1.0 / (driver_unique_customers.astype(float) + 1.0)).clip(0, 1)
    finalized["expected_share_customer"] = (1.0 / (customer_unique_drivers.astype(float) + 1.0)).clip(0, 1)

    raw_concentration = np.minimum(finalized["pair_share_driver"], finalized["pair_share_customer"]).clip(0, 1)
    expected_concentration = np.minimum(finalized["expected_share_driver"], finalized["expected_share_customer"]).clip(0, 1)
    concentration_gap = (
        (raw_concentration - expected_concentration)
        .div((1 - expected_concentration).replace(0, np.nan))
        .fillna(0.0)
        .clip(0, 1)
    )
    support_cap = max(float(config.min_extreme_trip_threshold), min(30.0, max(10.0, float(trip_threshold) * 1.5)))
    support_factor = np.clip(np.log1p(finalized["n_trips"].astype(float)) / np.log1p(support_cap), 0, 1)

    volume_ratio = finalized["n_trips"].astype(float).div(finalized["cohort_trip_threshold"].fillna(trip_threshold).clip(lower=1.0))
    finalized = finalized.assign(
        raw_concentration=raw_concentration.round(4),
        expected_concentration=expected_concentration.round(4),
        concentration_gap=concentration_gap.round(4),
        support_factor=support_factor.round(4),
        trip_threshold=trip_threshold,
        volume_score=(volume_ratio.clip(0, 3) / 3).round(4),
        is_extreme_volume=finalized["n_trips"] >= finalized["cohort_trip_threshold"],
        concentration_score=(concentration_gap * support_factor).clip(0, 1).round(4),
    )
    return finalized


def build_pair_stats(
    active_orders: pd.DataFrame,
    config: RideCollusionGraphConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, float]:
    config.validate()
    if active_orders.empty:
        empty = pd.DataFrame(
            columns=[
                "driver_id",
                "customer_id",
                "n_trips",
                "n_ghost",
                "ghost_rate",
                "avg_gmv",
                "total_gmv",
                "total_discount",
                "active_days",
                "latest_order_date",
                "top_service_name",
                "top_pickup_province_name",
                "top_dropoff_province_name",
                "driver_trip_count",
                "customer_trip_count",
                "pair_share_driver",
                "pair_share_customer",
                "raw_concentration",
                "expected_concentration",
                "concentration_gap",
                "support_factor",
                "trip_threshold",
                "volume_cohort",
                "cohort_trip_threshold",
                "trip_count_percentile",
                "volume_score",
                "is_extreme_volume",
                "concentration_score",
            ]
        )
        return empty, pd.DataFrame(), float(config.min_extreme_trip_threshold)

    pair_counts = (
        active_orders.groupby(["driver_id", "customer_id"], dropna=False)
        .size()
        .rename("n_trips")
        .reset_index()
    )
    raw_threshold = float(pair_counts["n_trips"].quantile(config.extreme_trip_quantile))
    trip_threshold = float(max(config.min_extreme_trip_threshold, raw_threshold))

    driver_counts = active_orders.groupby("driver_id").size().rename("driver_trip_count")
    customer_counts = active_orders.groupby("customer_id").size().rename("customer_trip_count")

    pair_stats = (
        active_orders.groupby(["driver_id", "customer_id"], dropna=False)
        .agg(
            n_trips=("order_id", "nunique"),
            n_ghost=("is_ghost", "sum"),
            avg_gmv=("gmv", "mean"),
            total_gmv=("gmv", "sum"),
            total_discount=("discount", "sum"),
            active_days=("order_date", "nunique"),
            latest_order_date=("order_date", "max"),
            top_service_name=("service_name", _mode_or_first),
            top_pickup_province_name=("pickup_province_name", _mode_or_first),
            top_dropoff_province_name=("last_dropoff_province_name", _mode_or_first),
        )
        .reset_index()
    )
    pair_stats = pair_stats.assign(ghost_rate=_safe_ratio(pair_stats["n_ghost"], pair_stats["n_trips"]))
    pair_stats = pair_stats.merge(driver_counts.rename_axis("driver_id").reset_index(), on="driver_id", how="left")
    pair_stats = pair_stats.merge(customer_counts.rename_axis("customer_id").reset_index(), on="customer_id", how="left")
    pair_stats = pair_stats.assign(
        pair_share_driver=_safe_ratio(pair_stats["n_trips"], pair_stats["driver_trip_count"]),
        pair_share_customer=_safe_ratio(pair_stats["n_trips"], pair_stats["customer_trip_count"]),
    )

    pair_stats = finalize_pair_stats(pair_stats, config, trip_threshold)
    return pair_stats.sort_values(["n_trips", "concentration_score"], ascending=False), pd.DataFrame(), trip_threshold


def shortlist_suspicious_pairs(
    pair_stats: pd.DataFrame,
    config: SuspiciousPairConfig | None = None,
) -> pd.DataFrame:
    suspicion_config = config or SuspiciousPairConfig()
    suspicion_config.validate()
    if pair_stats.empty:
        return pair_stats.copy()

    core_score = pair_stats["pair_core_score"] if "pair_core_score" in pair_stats.columns else 100 * (
        0.45 * pair_stats["volume_score"] + 0.55 * pair_stats["concentration_score"]
    )
    suspicious_mask = (
        (pair_stats["n_trips"] >= suspicion_config.min_pair_trips)
        & (
            pair_stats["is_extreme_volume"]
            | (pair_stats["concentration_score"] >= suspicion_config.min_concentration_score)
            | (core_score >= suspicion_config.min_pair_core_score)
        )
    )
    return pair_stats.loc[suspicious_mask].copy().sort_values(
        ["pair_core_score", "n_trips", "concentration_score"],
        ascending=False,
    )


def enrich_suspicious_pair_details(
    active_orders: pd.DataFrame,
    suspicious_pairs: pd.DataFrame,
) -> pd.DataFrame:
    if suspicious_pairs.empty:
        result = suspicious_pairs.copy()
        result["min_gap_min"] = pd.Series(dtype=float)
        result["dominant_route_key"] = pd.Series(dtype="string")
        result["dominant_route_trip_count"] = pd.Series(dtype="int64")
        result["dominant_route_share"] = pd.Series(dtype=float)
        return result

    candidate_orders = active_orders.merge(
        suspicious_pairs[["driver_id", "customer_id"]],
        on=["driver_id", "customer_id"],
        how="inner",
    ).copy()
    candidate_orders = candidate_orders.sort_values(["driver_id", "customer_id", "order_time_local_tz"]).assign(
        gap_min=(
            candidate_orders.groupby(["driver_id", "customer_id"], dropna=False)["order_time_local_tz"]
            .diff()
            .dt.total_seconds()
            .div(60.0)
        )
    )

    gap_stats = (
        candidate_orders.groupby(["driver_id", "customer_id"], dropna=False)
        .agg(min_gap_min=("gap_min", "min"))
        .reset_index()
    )

    route_counts = (
        candidate_orders.groupby(["driver_id", "customer_id", "route_key"], dropna=False)
        .size()
        .rename("dominant_route_trip_count")
        .reset_index()
        .sort_values(
            ["driver_id", "customer_id", "dominant_route_trip_count", "route_key"],
            ascending=[True, True, False, True],
        )
    )
    dominant_routes = route_counts.drop_duplicates(["driver_id", "customer_id"]).rename(columns={"route_key": "dominant_route_key"})

    enriched = suspicious_pairs.merge(gap_stats, on=["driver_id", "customer_id"], how="left")
    enriched = enriched.merge(
        dominant_routes[["driver_id", "customer_id", "dominant_route_key", "dominant_route_trip_count"]],
        on=["driver_id", "customer_id"],
        how="left",
    )
    enriched.loc[:, "dominant_route_trip_count"] = enriched["dominant_route_trip_count"].fillna(0).astype(int)
    enriched.loc[:, "dominant_route_share"] = _safe_ratio(enriched["dominant_route_trip_count"], enriched["n_trips"])
    return enriched
