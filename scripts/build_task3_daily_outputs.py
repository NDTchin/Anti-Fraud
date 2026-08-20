from __future__ import annotations

import argparse
import glob
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from src.algorithms.ride_collusion_graph import (
    RideCollusionGraphConfig,
    enrich_suspicious_pair_details,
    finalize_pair_stats,
    prepare_active_orders,
    shortlist_suspicious_pairs,
)
from src.rules.ride_kbc_rules import KbcRuleConfig, annotate_kbc_signals, apply_kbc_rules
from src.scoring.ride_collusion_scoring import (
    build_pair_scoring_features,
    build_flagged_orders,
    enrich_pair_graph_features,
    evaluate_known_pairs,
    finalize_business_rule_assignment,
    score_pairs,
    score_business_rules,
)


LEGACY_SCORE_COLUMNS = [
    "rule_score_base",
    "rule_score",
    "graph_risk_score",
    "final_risk_score",
]

ORDER_COLUMNS = [
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

STALE_REPORT_FILES = {
    "anomaly_scores.parquet",
    "daily_rule_summary.csv",
    "graph_entity_degree_report.csv",
    "graph_quality_report.csv",
    "graph_signal_summary.csv",
    "known_case_evaluation.csv",
    "pair_evidence.csv",
    "priority_recommendations.csv",
    "quality_report.csv",
    "rule_model_comparison.csv",
    "suspicious_components.csv",
}


def _resolve_input_paths(path: Path) -> list[Path]:
    raw_path = str(path)
    if any(char in raw_path for char in "*?[]"):
        return [Path(match) for match in sorted(glob.glob(raw_path))]
    if path.is_dir():
        return sorted(candidate for candidate in path.glob("*.parquet") if candidate.is_file())
    return [path]


def _iter_order_batches(path: Path, batch_size: int = 250_000):
    for input_path in _resolve_input_paths(path):
        available_columns = set(pq.read_schema(input_path).names)
        selected_columns = [column for column in ORDER_COLUMNS if column in available_columns]
        parquet_file = pq.ParquetFile(input_path)
        for batch in parquet_file.iter_batches(batch_size=batch_size, columns=selected_columns, use_threads=True):
            frame = batch.to_pandas()
            for column in ORDER_COLUMNS:
                if column not in frame.columns:
                    frame[column] = pd.NA
            yield frame[ORDER_COLUMNS]


def _prepare_active_batch(frame: pd.DataFrame) -> pd.DataFrame:
    working = frame.copy()
    if working["order_date"].isna().all():
        working["order_date"] = pd.to_datetime(working["order_time_local_tz"], errors="coerce").dt.date
    else:
        derived_order_date = pd.to_datetime(working["order_time_local_tz"], errors="coerce").dt.date
        working["order_date"] = pd.to_datetime(working["order_date"], errors="coerce").dt.date.fillna(derived_order_date)
    working["order_time_local_tz"] = pd.to_datetime(working["order_time_local_tz"], errors="coerce")
    working["pickup_completed_at_local_tz"] = pd.to_datetime(working["pickup_completed_at_local_tz"], errors="coerce")
    working["complete_time_local_tz"] = pd.to_datetime(working["complete_time_local_tz"], errors="coerce")
    return prepare_active_orders(working)


def _aggregate_batch_counts(active_batch: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    pair_counts = (
        active_batch.groupby(["driver_id", "customer_id"], dropna=False)
        .agg(n_trips=("order_id", "size"), n_ghost=("is_ghost", "sum"))
        .reset_index()
    )
    driver_counts = active_batch.groupby("driver_id", dropna=False).size().rename("driver_trip_count").reset_index()
    customer_counts = active_batch.groupby("customer_id", dropna=False).size().rename("customer_trip_count").reset_index()
    cohort_votes = (
        active_batch.groupby(["driver_id", "customer_id", "service_name", "pickup_province_name"], dropna=False)
        .size()
        .rename("cohort_votes")
        .reset_index()
    )
    return pair_counts, driver_counts, customer_counts, cohort_votes


def _combine_counts(frames: list[pd.DataFrame], group_columns: list[str], agg_column_map: dict[str, str]) -> pd.DataFrame:
    if not frames:
        return pd.DataFrame(columns=[*group_columns, *agg_column_map.keys()])
    combined = pd.concat(frames, ignore_index=True)
    aggregations = {column: aggregation for column, aggregation in agg_column_map.items()}
    return combined.groupby(group_columns, dropna=False).agg(aggregations).reset_index()


def _build_pair_stats_streaming(input_path: Path, graph_config: RideCollusionGraphConfig) -> tuple[pd.DataFrame, int, int, float]:
    pair_frames: list[pd.DataFrame] = []
    driver_frames: list[pd.DataFrame] = []
    customer_frames: list[pd.DataFrame] = []
    cohort_frames: list[pd.DataFrame] = []
    raw_rows = 0
    active_rows = 0
    for raw_batch in _iter_order_batches(input_path):
        raw_rows += len(raw_batch)
        active_batch = _prepare_active_batch(raw_batch)
        active_rows += len(active_batch)
        if active_batch.empty:
            continue
        pair_counts, driver_counts, customer_counts, cohort_votes = _aggregate_batch_counts(active_batch)
        pair_frames.append(pair_counts)
        driver_frames.append(driver_counts)
        customer_frames.append(customer_counts)
        cohort_frames.append(cohort_votes)

    pair_stats = _combine_counts(pair_frames, ["driver_id", "customer_id"], {"n_trips": "sum", "n_ghost": "sum"})
    if pair_stats.empty:
        return pair_stats, raw_rows, active_rows, float(graph_config.min_extreme_trip_threshold)

    driver_counts = _combine_counts(driver_frames, ["driver_id"], {"driver_trip_count": "sum"})
    customer_counts = _combine_counts(customer_frames, ["customer_id"], {"customer_trip_count": "sum"})
    cohort_votes = _combine_counts(
        cohort_frames,
        ["driver_id", "customer_id", "service_name", "pickup_province_name"],
        {"cohort_votes": "sum"},
    )
    top_cohort = (
        cohort_votes.sort_values(["driver_id", "customer_id", "cohort_votes"], ascending=[True, True, False])
        .drop_duplicates(["driver_id", "customer_id"])
        .rename(columns={"service_name": "top_service_name", "pickup_province_name": "top_pickup_province_name"})
    )

    raw_threshold = float(pair_stats["n_trips"].quantile(graph_config.extreme_trip_quantile))
    trip_threshold = float(max(graph_config.min_extreme_trip_threshold, raw_threshold))
    pair_stats = pair_stats.merge(driver_counts, on="driver_id", how="left").merge(customer_counts, on="customer_id", how="left")
    pair_stats = pair_stats.merge(top_cohort[["driver_id", "customer_id", "top_service_name", "top_pickup_province_name"]], on=["driver_id", "customer_id"], how="left")
    pair_stats["pair_share_driver"] = pair_stats["n_trips"].astype(float).div(pair_stats["driver_trip_count"].replace(0, pd.NA)).fillna(0.0)
    pair_stats["pair_share_customer"] = pair_stats["n_trips"].astype(float).div(pair_stats["customer_trip_count"].replace(0, pd.NA)).fillna(0.0)
    pair_stats["ghost_rate"] = pair_stats["n_ghost"].astype(float).div(pair_stats["n_trips"].replace(0, pd.NA)).fillna(0.0)

    pair_stats = finalize_pair_stats(pair_stats, graph_config, trip_threshold)
    return pair_stats.sort_values(["n_trips", "concentration_score"], ascending=False), raw_rows, active_rows, trip_threshold


def _load_candidate_orders(input_path: Path, suspicious_pairs: pd.DataFrame) -> pd.DataFrame:
    if suspicious_pairs.empty:
        return pd.DataFrame(columns=ORDER_COLUMNS)
    pair_keys = set(
        suspicious_pairs["driver_id"].astype("string").str.strip() + "||" + suspicious_pairs["customer_id"].astype("string").str.strip()
    )
    candidate_frames: list[pd.DataFrame] = []
    for raw_batch in _iter_order_batches(input_path):
        active_batch = _prepare_active_batch(raw_batch)
        if active_batch.empty:
            continue
        keys = active_batch["driver_id"].astype("string").str.strip() + "||" + active_batch["customer_id"].astype("string").str.strip()
        filtered = active_batch.loc[keys.isin(pair_keys)].copy()
        if not filtered.empty:
            candidate_frames.append(filtered)
    return pd.concat(candidate_frames, ignore_index=True) if candidate_frames else pd.DataFrame(columns=ORDER_COLUMNS)


def _enrich_pair_rollups_from_candidate_orders(candidate_orders: pd.DataFrame, suspicious_pairs: pd.DataFrame) -> pd.DataFrame:
    if suspicious_pairs.empty:
        return suspicious_pairs.copy()
    rollups = (
        candidate_orders.groupby(["driver_id", "customer_id"], dropna=False)
        .agg(
            avg_gmv=("gmv", "mean"),
            total_gmv=("gmv", "sum"),
            total_discount=("discount", "sum"),
            active_days=("order_date", "nunique"),
            latest_order_date=("order_date", "max"),
            top_service_name=("service_name", lambda values: values.dropna().mode().iloc[0] if not values.dropna().mode().empty else pd.NA),
            top_pickup_province_name=("pickup_province_name", lambda values: values.dropna().mode().iloc[0] if not values.dropna().mode().empty else pd.NA),
            top_dropoff_province_name=("last_dropoff_province_name", lambda values: values.dropna().mode().iloc[0] if not values.dropna().mode().empty else pd.NA),
        )
        .reset_index()
    )
    merged = suspicious_pairs.merge(rollups, on=["driver_id", "customer_id"], how="left", suffixes=("", "_rollup"))
    for column in (
        "avg_gmv",
        "total_gmv",
        "total_discount",
        "active_days",
        "latest_order_date",
        "top_service_name",
        "top_pickup_province_name",
        "top_dropoff_province_name",
    ):
        rollup_column = f"{column}_rollup"
        if rollup_column in merged.columns:
            if column in merged.columns:
                merged[column] = merged[column].fillna(merged[rollup_column])
                merged = merged.drop(columns=[rollup_column])
            else:
                merged = merged.rename(columns={rollup_column: column})
    return merged


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build daily Task 3 outputs for ride collusion rules.")
    parser.add_argument(
        "--input",
        default="data/handoff/ride/cleaned_orders/orders_ride_masked_2026-07-2[4-9].parquet",
        help="Path, directory, or glob pattern for ride cleaned-orders parquet file(s).",
    )
    parser.add_argument(
        "--report-dir",
        default="reports/task3",
        help="Directory where dashboard-ready outputs should be written.",
    )
    parser.add_argument(
        "--known-pairs",
        default="data/handoff/ride/known_cases/kbc_known_pairs.csv",
        help="Optional CSV of known collusion pairs with columns driver_id and customer_id.",
    )
    return parser.parse_args()


def _build_outputs_for_single_input(input_path: Path, known_pairs_path: Path) -> dict[str, pd.DataFrame]:
    graph_config = RideCollusionGraphConfig()
    rule_config = KbcRuleConfig()
    all_pair_stats, raw_order_count, active_order_count, trip_threshold = _build_pair_stats_streaming(input_path, graph_config)
    all_pair_stats = score_pairs(all_pair_stats)
    suspicious_pairs = shortlist_suspicious_pairs(all_pair_stats)
    candidate_orders = _load_candidate_orders(input_path, suspicious_pairs)
    suspicious_pairs = _enrich_pair_rollups_from_candidate_orders(candidate_orders, suspicious_pairs)
    suspicious_pairs = enrich_suspicious_pair_details(candidate_orders, suspicious_pairs)
    suspicious_pairs = annotate_kbc_signals(suspicious_pairs, rule_config)
    suspicious_pairs = build_pair_scoring_features(suspicious_pairs)
    suspicious_pairs = enrich_pair_graph_features(candidate_orders, suspicious_pairs)
    suspicious_pairs = score_business_rules(suspicious_pairs)
    pair_reason_rows = apply_kbc_rules(suspicious_pairs, rule_config)
    suspicious_pairs = finalize_business_rule_assignment(suspicious_pairs, pair_reason_rows)
    if not pair_reason_rows.empty:
        pair_reason_rows = pair_reason_rows.merge(
            suspicious_pairs[
                [
                    "driver_id",
                    "customer_id",
                    "primary_business_rule",
                    "primary_business_rule_label",
                    "primary_business_rule_story",
                    "primary_business_rule_score",
                    "triggered_business_rules",
                    "triggered_reason_codes",
                    "repeated_pair_rule_score",
                    "ghost_trip_rule_score",
                    "route_farming_rule_score",
                    "network_pattern_rule_score",
                ]
            ],
            on=["driver_id", "customer_id"],
            how="left",
            suffixes=("", "_pair"),
        )
    flagged_orders = build_flagged_orders(candidate_orders, pair_reason_rows)
    known_pairs = pd.read_csv(known_pairs_path) if known_pairs_path.exists() else pd.DataFrame()
    known_case_evaluation = evaluate_known_pairs(flagged_orders, known_pairs)
    pair_summary = suspicious_pairs.sort_values(["priority_score", "pair_core_score", "n_trips"], ascending=False)
    pair_summary = pair_summary.drop(columns=[column for column in LEGACY_SCORE_COLUMNS if column in pair_summary.columns], errors="ignore")
    pair_reason_rows = pair_reason_rows.drop(columns=[column for column in LEGACY_SCORE_COLUMNS if column in pair_reason_rows.columns], errors="ignore")
    flagged_orders = flagged_orders.drop(columns=[column for column in LEGACY_SCORE_COLUMNS if column in flagged_orders.columns], errors="ignore")
    return {
        "raw_order_count": pd.DataFrame([{"value": raw_order_count}]),
        "active_order_count": pd.DataFrame([{"value": active_order_count}]),
        "candidate_orders": candidate_orders,
        "all_pair_stats": all_pair_stats,
        "pair_stats": suspicious_pairs,
        "pair_reason_rows": pair_reason_rows,
        "flagged_orders": flagged_orders,
        "known_case_evaluation": known_case_evaluation,
    }


def _concat_frames(frames: list[pd.DataFrame]) -> pd.DataFrame:
    valid_frames = [frame for frame in frames if frame is not None and not frame.empty]
    if not valid_frames:
        return pd.DataFrame()
    return pd.concat(valid_frames, ignore_index=True)


def build_outputs(input_path: Path, report_dir: Path, known_pairs_path: Path) -> dict[str, pd.DataFrame]:
    input_paths = _resolve_input_paths(input_path)
    per_day_outputs = [_build_outputs_for_single_input(single_input_path, known_pairs_path) for single_input_path in input_paths]

    raw_order_total = sum(
        int(output["raw_order_count"].iloc[0]["value"]) for output in per_day_outputs if not output["raw_order_count"].empty
    )
    active_order_total = sum(
        int(output["active_order_count"].iloc[0]["value"]) for output in per_day_outputs if not output["active_order_count"].empty
    )

    combined_candidate_orders = _concat_frames([output["candidate_orders"] for output in per_day_outputs])
    combined_all_pair_stats = _concat_frames([output["all_pair_stats"] for output in per_day_outputs])
    combined_pair_stats = _concat_frames([output["pair_stats"] for output in per_day_outputs])
    combined_pair_reason_rows = _concat_frames([output["pair_reason_rows"] for output in per_day_outputs])
    combined_flagged_orders = _concat_frames([output["flagged_orders"] for output in per_day_outputs])
    combined_known_case_evaluation = _concat_frames([output["known_case_evaluation"] for output in per_day_outputs])

    report_dir.mkdir(parents=True, exist_ok=True)
    combined_flagged_orders.to_parquet(report_dir / "flagged_orders.parquet", index=False)
    combined_pair_stats.to_csv(report_dir / "kbc_pair_summary.csv", index=False)
    combined_pair_reason_rows.to_csv(report_dir / "kbc_pair_reasons.csv", index=False)
    for filename in sorted(STALE_REPORT_FILES):
        stale_path = report_dir / filename
        if stale_path.exists():
            stale_path.unlink()

    return {
        "raw_order_count": pd.DataFrame([{"value": raw_order_total}]),
        "active_order_count": pd.DataFrame([{"value": active_order_total}]),
        "candidate_orders": combined_candidate_orders,
        "all_pair_stats": combined_all_pair_stats,
        "pair_stats": combined_pair_stats,
        "pair_reason_rows": combined_pair_reason_rows,
        "flagged_orders": combined_flagged_orders,
        "known_case_evaluation": combined_known_case_evaluation,
    }


def main() -> None:
    args = parse_args()
    outputs = build_outputs(Path(args.input), Path(args.report_dir), Path(args.known_pairs))
    pair_stats = outputs["pair_stats"]
    flagged_orders = outputs["flagged_orders"]

    active_order_count = int(outputs["active_order_count"].iloc[0]["value"]) if not outputs["active_order_count"].empty else 0
    print(f"Built collusion outputs for {active_order_count:,} active ride orders.")
    print(f"Extreme trip threshold (q=0.9999): {pair_stats['trip_threshold'].iloc[0] if not pair_stats.empty else 'n/a'}")
    print(f"Flagged candidate pairs: {pair_stats[['driver_id', 'customer_id']].drop_duplicates().shape[0]:,}")
    print(f"Flagged order rows: {len(flagged_orders):,}")
    if not outputs["known_case_evaluation"].empty:
        hit_rate = outputs["known_case_evaluation"]["is_flagged"].mean()
        print(f"Known-pair hit rate: {hit_rate:.2%}")


if __name__ == "__main__":
    main()
