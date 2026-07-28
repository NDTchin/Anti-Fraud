# Sprint 2 Scope: KB-C Driver-Customer Ghost-Trip Collusion

## Problem statement

Sprint 2 is now focused on one concrete ride-fraud pattern:

- driver and customer collude to create fake trips
- the same pair repeats at extreme frequency
- some trips show `avg_kmh = 0`
- consecutive trips can be created too quickly to be operationally plausible

The working entity in graph terms is the weighted edge `(Driver)-[SERVED]->(Order)<-[PLACED]-(Customer)`, aggregated into a driver-customer pair.

## Graph algorithms that fit this problem

Recommended graph-first techniques for this problem:

1. Weighted bipartite edge outlier detection
   Use the trip count on each `(driver_id, customer_id)` edge.
   This is the strongest first-pass signal for collusion because fake-trip farming usually concentrates on a small number of pairs.

2. Pair concentration on each endpoint
   Measure how much of a driver's activity and how much of a customer's activity is absorbed by the same counterpart.
   This is equivalent to checking whether one weighted edge dominates both endpoint neighborhoods.

3. Temporal edge anomaly
   Treat consecutive trips on the same edge as a time series and flag unrealistically short repeat gaps.
   This is the best operational signal for “đơn ảo/tạo quá nhanh”.

4. Community detection on suspicious subgraph
   After filtering suspicious pairs, run WCC or Louvain on the induced graph of drivers, customers, and shared addresses/routes.
   This helps separate isolated collusion pairs from larger farming rings.

5. Node similarity / route reuse
   Compare suspicious pairs by shared pickup-dropoff loops, shared promo behavior, or shared payment patterns.
   This is useful for clustering multiple fake-trip scripts that reuse the same operating template.

## Rules implemented on real ride data

Implementation lives in:

- [src/algorithms/ride_collusion_graph.py](/D:/VSF/src/algorithms/ride_collusion_graph.py)
- [src/rules/ride_kbc_rules.py](/D:/VSF/src/rules/ride_kbc_rules.py)
- [src/scoring/ride_collusion_scoring.py](/D:/VSF/src/scoring/ride_collusion_scoring.py)
- [scripts/build_task3_daily_outputs.py](/D:/VSF/scripts/build_task3_daily_outputs.py)

Current rule family:

1. `KB-C_EXTREME_VOLUME`
   Group by `(driver_id, customer_id)`.
   Compute `n_trips`.
   Flag pairs with `n_trips > quantile(0.9999)` in the active 4-day window.

2. `KB-C_HIGH_GHOST_RATE`
   Compute `n_ghost` where `avg_kmh = 0`.
   Compute `ghost_rate = n_ghost / n_trips`.
   Flag pairs with `ghost_rate > 0.3`.

3. `KB-C_SUPERFAST_GAP`
   Sort each pair by `order_time_local_tz`.
   Compute `min_gap_min` between consecutive trips.
   Flag pairs with `min_gap_min < 5`.

4. `KB-C_TIGHT_PAIR_SHARE`
   Compute `pair_share_driver = n_trips / total_driver_trips`.
   Compute `pair_share_customer = n_trips / total_customer_trips`.
   Flag pairs that dominate both endpoints in the same window.

5. `KB-C_ROUTE_LOOP`
   Compute the dominant pickup-dropoff route per pair.
   Flag pairs whose dominant route absorbs at least half of trips.

High-confidence logic:

- `high_confidence = (ghost_rate > 0.3) OR (min_gap_min < 5)`

## Real-data run on July 27, 2026

Command used:

```powershell
python -m scripts.build_task3_daily_outputs --report-dir reports/task3
```

Core run stats from the current 4-day ride file:

- active completed ride orders: `4,767,940`
- unique driver-customer pairs: `4,621,522`
- extreme trip threshold at `quantile(0.9999)`: `12`
- candidate suspicious pairs above threshold: `371`
- flagged order rows written to dashboard output: `11,000`

Pair-level reason counts:

- `KB-C_EXTREME_VOLUME`: `371` pairs
- `KB-C_TIGHT_PAIR_SHARE`: `244` pairs
- `KB-C_SUPERFAST_GAP`: `47` pairs
- `KB-C_HIGH_GHOST_RATE`: `26` pairs
- `KB-C_ROUTE_LOOP`: `6` pairs

Daily order counts in dashboard output:

- `2026-07-14`: `1,252`
- `2026-07-15`: `1,524`
- `2026-07-16`: `1,486`
- `2026-07-17`: `1,523`

## Known-case evaluation

Known-case seed file:

- [data/handoff/ride/known_cases/kbc_known_pairs.csv](/D:/VSF/data/handoff/ride/known_cases/kbc_known_pairs.csv)

The provided real example pair was added as a seed known case and was successfully flagged.

Observed seeded case:

- pair: `652280701c4d0c32` + `0cb58995c54abba0`
- `n_trips = 64`
- `avg_gmv = 12,390.625`
- `min_gap_min = 0.9`
- hit reasons include `KB-C_EXTREME_VOLUME` and `KB-C_SUPERFAST_GAP`

## Dashboard outputs

The script writes dashboard-ready files into [reports/task3](/D:/VSF/reports/task3):

- `daily_rule_summary.csv`
- `rule_model_comparison.csv`
- `priority_recommendations.csv`
- `quality_report.csv`
- `flagged_orders.parquet`
- `anomaly_scores.parquet`
- `kbc_pair_summary.csv`
- `kbc_pair_reasons.csv`
- `known_case_evaluation.csv`

These outputs are already compatible with [src/dashboard/app.py](/D:/VSF/src/dashboard/app.py).
