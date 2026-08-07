# Ride Daily Import To Neo4j

## Purpose

Tai lieu nay mo ta luong import `ride` vao Neo4j trong boi canh project duoc dinh huong lai theo bai toan:

- `Driver-Customer Ghost-Trip Collusion`

Tai lieu nay khong chi mo ta cach nap du lieu, ma con chi ro importer can phuc vu nhung gi cho `graph core` moi.

## Graph-core view of the data

Huong moi cua project xem pair `driver-customer` la don vi phan tich trung tam.

Vi vay, importer can dam bao graph order-level co du cac lien ket de downstream co the tong hop thanh:

- `trip_count` theo pair
- `driver_trip_count`
- `customer_trip_count`
- cac shared entities de build suspicious graph

Nhap du lieu vao Neo4j van o cap `Order`, nhung muc tieu nghiep vu cuoi cung la suy ra:

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

Moi batch se:

- bo qua record khong co `order_id`
- `MERGE` `Order` theo `order_id`
- `MERGE` `Customer`
- `MERGE` `Driver`
- `MERGE` `Address`
- `MERGE` `PaymentMethod`
- `MERGE` `PromotionCode`
- `MERGE` `PromotionCampaign`

Va tao cac quan he can thiet nhu:

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

Mac du graph core moi phan tich o cap pair, importer order-level van can thiet vi no cung cap:

- quan he `Customer -> Order`
- quan he `Driver -> Order`
- pickup/dropoff addresses
- payment va promo reuse
- service taxonomy de filter phan tich

Day la nen du lieu de build 2 lop graph:

1. `pair graph`
2. `suspicious graph`

## Minimum data requirements for the new graph core

De phuc vu huong moi, importer va nguon cleaned data nen dam bao co toi thieu:

- `order_id`
- `driver_id`
- `customer_id`
- `order_time_local_tz`
- trang thai de xac dinh order hop le cho phan tich trip

De phuc vu suspicious graph va WCC, nen co them:

- pickup address
- dropoff address
- payment method
- promotion code

De phuc vu enrichment sau nay, co the co them:

- `avg_kmh`
- route-related fields
- GMV, discount, operational metrics

## Recommended downstream aggregation after import

Sau khi import vao Neo4j, downstream khong nen dung lai o order graph.

Can co mot buoc aggregate de tao:

1. `pair table`
2. `suspicious pair list`
3. `suspicious graph` noi bang shared entities

Tuong ung voi huong graph core:

- `weighted edge outlier detection`
- `bipartite concentration scoring`
- `WCC`

## Quality counters

Script hien ghi nhan cac chi so:

- `missing_order_id`
- `missing_customer_id`
- `missing_order_time_local_tz`
- `duplicate_order_id`
- `new_orders`
- `updated_orders`

Trong huong moi, cac check nay van dung, nhung ve nghiep vu fraud thi can hieu:

- thieu `driver_id` hoac `customer_id` se anh huong truc tiep den kha nang build pair graph
- thieu `payment` hoac `address` se lam yeu suspicious graph

## Example

```powershell
docker compose -f infra/docker-compose.full.yml up -d neo4j

python -m scripts.import_ride_daily_to_neo4j `
  --source data\handoff\ride\cleaned_orders\orders_ride_masked_2026-07-2[4-9].parquet `
  --batch-size 2000
```

## Final note

Importer nay nen duoc xem la lop ha tang du lieu cho huong graph moi, khong phai ban than bo detector.

Gia tri cua no trong project duoc reset scope la:

- luu order graph sach va nhat quan
- bao ton cac shared entities quan trong
- cho phep aggregate len pair graph va suspicious graph mot cach on dinh
