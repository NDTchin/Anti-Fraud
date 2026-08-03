# Ride Daily Import To Neo4j

## Purpose

Tài liệu này mô tả luồng import `ride` hiện tại của project. Luồng này dùng
incremental upsert vào Neo4j đang chạy, phù hợp với nhu cầu nạp dữ liệu theo
ngày.

## Current Flow

```text
Cleaned ride orders (.parquet / .csv)
        |
Read by batch
        |
Basic quality checks
        |
Normalize row values
        |
Build address keys
        |
MERGE nodes and relationships into Neo4j
```

## Entry points

- script chính: `scripts/import_ride_daily_to_neo4j.py`
- runner: `scripts/run_ride_import.ps1`
- constraints: `src/graph/cypher/001_constraints.cypher`

## Supported input

- `.parquet`
- `.csv`

## Import behavior

Mỗi batch sẽ:

- bỏ qua record không có `order_id`
- `MERGE` `Order` theo `order_id`
- `MERGE` `Customer`, `Driver`, `Address`, `PaymentMethod`, `PromotionCode`, `PromotionCampaign`
- `MERGE` các quan hệ:
  - `PLACED`
  - `SERVED`
  - `PICKUP_AT`
  - `DROPOFF_AT`
  - `PAID_BY`
  - `USED_PROMO`
  - `IN_CAMPAIGN`
  - `CANCELLED_BY`
  - `HAS_CANCEL_REASON`
  - `USES_SERVICE`
  - `USES_SERVICE_TYPE`
  - `USES_SUB_VERTICAL`
  - `USES_TRAVEL_MODE`
  - `USES_CHANNEL_TYPE`

## Quality counters

Script hiện ghi nhận các chỉ số:

- `missing_order_id`
- `missing_customer_id`
- `missing_order_time_local_tz`
- `duplicate_order_id`
- `new_orders`
- `updated_orders`

## Example

```powershell
docker compose -f infra/docker-compose.full.yml up -d neo4j

python -m scripts.import_ride_daily_to_neo4j `
  --source data\handoff\ride\cleaned_orders\orders_ride_clean_2026-07-14_to_17.parquet `
  --batch-size 2000
```
