from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.algorithms.ride_collusion_graph import (
    RideCollusionGraphConfig,
    build_pair_stats,
    load_ride_orders,
    prepare_active_orders,
)
from src.rules.ride_kbc_rules import KbcRuleConfig, annotate_kbc_signals, apply_kbc_rules
from src.scoring.ride_collusion_scoring import (
    build_flagged_orders,
    enrich_pair_graph_features,
    build_priority_recommendations,
    build_quality_report,
    build_rule_model_comparison,
    evaluate_known_pairs,
    score_pairs,
    summarize_daily_flags,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build daily Task 3 outputs for ride collusion rules.")
    parser.add_argument(
        "--input",
        default="data/handoff/ride/cleaned_orders/orders_ride_clean_2026-07-14_to_17.parquet",
        help="Path to the ride cleaned-orders parquet file.",
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


def build_outputs(input_path: Path, report_dir: Path, known_pairs_path: Path) -> dict[str, pd.DataFrame]:
    raw_orders = load_ride_orders(input_path)
    active_orders = prepare_active_orders(raw_orders)
    graph_config = RideCollusionGraphConfig()
    rule_config = KbcRuleConfig()
    pair_stats, _, trip_threshold = build_pair_stats(active_orders, graph_config)
    pair_stats = annotate_kbc_signals(pair_stats, rule_config)
    pair_stats = score_pairs(pair_stats)
    pair_stats = enrich_pair_graph_features(active_orders, pair_stats)
    pair_reason_rows = apply_kbc_rules(pair_stats, rule_config)
    flagged_orders = build_flagged_orders(active_orders, pair_reason_rows)

    daily_summary = summarize_daily_flags(flagged_orders)
    comparison = build_rule_model_comparison(flagged_orders)
    recommendations = build_priority_recommendations(flagged_orders)
    quality = build_quality_report(raw_orders, active_orders, pair_stats, trip_threshold, flagged_orders)
    anomaly_scores = pd.DataFrame(
        columns=[
            "domain",
            "order_id",
            "customer_id",
            "model_name",
            "model_version",
            "anomaly_score",
            "is_model_anomaly",
            "score_threshold",
            "scored_at",
            "top_features",
        ]
    )

    known_pairs = pd.read_csv(known_pairs_path) if known_pairs_path.exists() else pd.DataFrame()
    known_case_evaluation = evaluate_known_pairs(flagged_orders, known_pairs)
    pair_summary = pair_stats.sort_values(["high_confidence", "n_trips", "rule_score"], ascending=False)

    report_dir.mkdir(parents=True, exist_ok=True)
    daily_summary.to_csv(report_dir / "daily_rule_summary.csv", index=False)
    comparison.to_csv(report_dir / "rule_model_comparison.csv", index=False)
    recommendations.to_csv(report_dir / "priority_recommendations.csv", index=False)
    quality.to_csv(report_dir / "quality_report.csv", index=False)
    flagged_orders.to_parquet(report_dir / "flagged_orders.parquet", index=False)
    anomaly_scores.to_parquet(report_dir / "anomaly_scores.parquet", index=False)
    pair_summary.to_csv(report_dir / "kbc_pair_summary.csv", index=False)
    pair_reason_rows.to_csv(report_dir / "kbc_pair_reasons.csv", index=False)
    if not known_case_evaluation.empty:
        known_case_evaluation.to_csv(report_dir / "known_case_evaluation.csv", index=False)

    return {
        "raw_orders": raw_orders,
        "active_orders": active_orders,
        "pair_stats": pair_stats,
        "pair_reason_rows": pair_reason_rows,
        "flagged_orders": flagged_orders,
        "daily_summary": daily_summary,
        "comparison": comparison,
        "recommendations": recommendations,
        "quality": quality,
        "known_case_evaluation": known_case_evaluation,
    }


def main() -> None:
    args = parse_args()
    outputs = build_outputs(Path(args.input), Path(args.report_dir), Path(args.known_pairs))
    pair_stats = outputs["pair_stats"]
    flagged_orders = outputs["flagged_orders"]

    print(f"Built collusion outputs for {len(outputs['active_orders']):,} active ride orders.")
    print(f"Extreme trip threshold (q=0.9999): {pair_stats['trip_threshold'].iloc[0] if not pair_stats.empty else 'n/a'}")
    print(f"Flagged candidate pairs: {pair_stats[['driver_id', 'customer_id']].drop_duplicates().shape[0]:,}")
    print(f"Flagged order rows: {len(flagged_orders):,}")
    if not outputs["known_case_evaluation"].empty:
        hit_rate = outputs["known_case_evaluation"]["is_flagged"].mean()
        print(f"Known-pair hit rate: {hit_rate:.2%}")


if __name__ == "__main__":
    main()
