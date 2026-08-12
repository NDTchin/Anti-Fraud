# Ride Daily Import To Neo4j

## Purpose

Tài liệu này mô tả luồng import `ride` vào Neo4j trong bối cảnh project được định hướng lại theo bài toán:

- `Driver-Customer Ghost-Trip Collusion`

Tài liệu này không chỉ mô tả cách nạp dữ liệu, mà còn chỉ rõ importer cần phục vụ những gì cho `graph core` mới.

## Graph-core view of the data

Hướng mới của project xem pair `driver-customer` là đơn vị phân tích trung tâm.

Vì vậy, importer cần đảm bảo graph order-level có đủ các liên kết để downstream có thể tổng hợp thành:

- `trip_count` theo pair
- `driver_trip_count`
- `customer_trip_count`
- các shared entities để build suspicious graph

Nhập dữ liệu vào Neo4j vẫn ở cấp `Order`, nhưng mục tiêu nghiệp vụ cuối cùng là suy ra:

- weighted edge giua `Driver` va `Customer`
- shared infrastructure xung quanh pair nghi ngo

## Current flow

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
MERGE order-centric graph into Neo4j
        |
Aggregate downstream into pair graph and suspicious graph
```

## Entry points

- script chinh: `scripts/import_ride_daily_to_neo4j.py`
- runner: `scripts/run_ride_import.ps1`
- constraints: `src/graph/cypher/001_constraints.cypher`

## Supported input

- `.parquet`
- `.csv`

## Import behavior

Mỗi batch sẽ:

- bỏ qua record không có `order_id`
- `MERGE` `Order` theo `order_id`
- `MERGE` `Customer`
- `MERGE` `Driver`
- `MERGE` `Address`
- `MERGE` `PaymentMethod`
- `MERGE` `PromotionCode`
- `MERGE` `PromotionCampaign`

Và tạo các quan hệ cần thiết như:

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

## Why this importer still matters in the new direction

Mặc dù graph core mới phân tích ở cấp pair, importer order-level vẫn cần thiết vì nó cung cấp:

- quan hệ `Customer -> Order`
- quan hệ `Driver -> Order`
- pickup/dropoff addresses
- payment và promo reuse
- service taxonomy để filter phân tích

Đây là nền dữ liệu để build 2 lớp graph:

1. `pair graph`
2. `suspicious graph`

## Minimum data requirements for the new graph core

Để phục vụ hướng mới, importer và nguồn cleaned data nên đảm bảo có tối thiểu:

- `order_id`
- `driver_id`
- `customer_id`
- `order_time_local_tz`
- trạng thái để xác định order hợp lệ cho phân tích trip

Để phục vụ suspicious graph và WCC, nên có thêm:

- pickup address
- dropoff address
- payment method
- promotion code

Để phục vụ enrichment sau này, có thể có thêm:

- `avg_kmh`
- route-related fields
- GMV, discount, operational metrics

## Recommended downstream aggregation after import

Sau khi import vào Neo4j, downstream không nên dừng lại ở order graph.

Cần có một bước aggregate để tạo:

1. `pair table`
2. `suspicious pair list`
3. `suspicious graph` nối bằng shared entities

Tuơng ứng với hướng graph core:

- `weighted edge outlier detection`
- `bipartite concentration scoring`
- `WCC`

## Quality counters

Script hiện ghi nhận các chỉ số:

- `missing_order_id`
- `missing_customer_id`
- `missing_order_time_local_tz`
- `duplicate_order_id`
- `new_orders`
- `updated_orders`

Trong hướng mới, các check này vẫn đúng, nhưng về nghiệp vụ fraud thì cần hiểu:

- thiếu `driver_id` hoặc `customer_id` sẽ ảnh hưởng trực tiếp đến khả năng build pair graph
- thiếu `payment` hoặc `address` sẽ làm yếu suspicious graph

## Example

```powershell
docker compose -f infra/docker-compose.full.yml up -d neo4j

python -m scripts.import_ride_daily_to_neo4j `
  --source data\handoff\ride\cleaned_orders\orders_ride_masked_2026-07-2[4-9].parquet `
  --batch-size 2000
```

## Final note

Importer này nên được xem là lớp hạ tầng dữ liệu cho hướng graph mới, không phải bản thân bộ detector.

Gia trị của nó trong project được reset scope là:

- lưu order graph sạch và nhất quán
- bảo tồn các shared entities quan trọng
- cho phép aggregate lên pair graph và suspicious graph một cách ổn định
