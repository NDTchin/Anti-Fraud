# Sprint 1 Report

## 1. Mục tiêu Sprint 1

Sprint 1 tập trung xây dựng nền tảng graph cho bài toán anti-fraud, gồm:

- xác định graph schema cho `food` và `ride`
- xây pipeline chuyển dữ liệu từ `SQL/CSV/Parquet` sang `Graph DB`
- import dữ liệu mẫu vào `Neo4j`
- viết một số query `Cypher` cơ bản để truy vấn quan hệ
- demo visualize một vài case fraud đã biết hoặc các cụm nghi vấn

## 2. Graph Schema

### 2.1. Schema chung

Các node chính:

- `Customer`
- `Order`
- `Driver`
- `Address`
- `PaymentMethod`
- `PromotionCode`
- `PromotionCampaign`

Các relationship chính:

- `(Customer)-[:PLACED]->(Order)`
- `(Driver)-[:SERVED]->(Order)`
- `(Order)-[:PICKUP_AT]->(Address)`
- `(Order)-[:DROPOFF_AT]->(Address)`
- `(Order)-[:PAID_BY]->(PaymentMethod)`
- `(Order)-[:USED_PROMO]->(PromotionCode)`
- `(PromotionCode)-[:IN_CAMPAIGN]->(PromotionCampaign)`

Các property quan trọng trên `Order`:

- `order_id`, `domain`, `order_status`
- `order_time_local_tz`, `complete_time_local_tz`
- `gmv`, `discount`, `commission`, `net_income`

### 2.2. Food graph schema

Ngoài schema chung, domain `food` có thêm:

- node `Merchant`
- relationship `(Order)-[:FROM_MERCHANT]->(Merchant)`

Các property quan trọng bổ sung:

- `merchant_id`
- `food_total_paid`
- `food_total_item_quantity`
- `lead_time_second`
- `vertical_name`
- `food_dispatch_type`

Ý nghĩa:

- `food` tập trung vào promo abuse, merchant concentration, repeated customer-driver, shared address, shared payment.

### 2.3. Ride graph schema

Domain `ride` dùng schema chung, chủ yếu tập trung vào:

- `Customer`
- `Order`
- `Driver`
- `Address`
- `PaymentMethod`
- `PromotionCode`

Các property quan trọng bổ sung:

- `declared_km`
- `actual_km`
- `km_diff` hoặc `km_ratio`
- `intrip_time_second`
- `service_name`
- `travel_mode`

Ý nghĩa:

- `ride` tập trung vào repeated customer-driver, shared payment, shared address, trip anomaly, promo abuse.

## 3. Pipeline Chuyển Dữ Liệu Từ SQL/CSV Sang Graph DB

Pipeline hiện tại:

1. đọc dữ liệu từ `SQL`, `.csv` hoặc `.parquet`
2. chuẩn hóa dữ liệu đầu vào
3. kiểm tra chất lượng dữ liệu:
   - thiếu `order_id`
   - thiếu `customer_id`
   - thiếu `order_time_local_tz`
   - trùng `order_id`
4. tách dữ liệu thành:
   - `nodes`
   - `relationships`
   - `headers` cho `neo4j-admin import`
5. sinh `manifest.json` và `quality_report.csv`
6. import vào `Neo4j`


## 4. Một Vài Query Cypher Cơ Bản

### 4.1. Tìm các order của một customer

```cypher
MATCH (c:Customer {customer_id: 'C001'})-[:PLACED]->(o:Order)
RETURN c, o
LIMIT 20;
```

### 4.2. Tìm customer dùng chung payment method

```cypher
MATCH (c:Customer)-[:PLACED]->(o:Order)-[:PAID_BY]->(p:PaymentMethod)
WITH p, collect(DISTINCT c.customer_id) AS customers
WHERE size(customers) > 1
RETURN p.name, customers, size(customers) AS customer_count
ORDER BY customer_count DESC
LIMIT 20;
```

### 4.3. Tìm customer dùng chung promo code

```cypher
MATCH (c:Customer)-[:PLACED]->(o:Order)-[:USED_PROMO]->(p:PromotionCode)
WITH p, collect(DISTINCT c.customer_id) AS customers
WHERE size(customers) > 1
RETURN p.code, customers, size(customers) AS customer_count
ORDER BY customer_count DESC
LIMIT 20;
```

### 4.4. Tìm repeated customer-driver pair

```cypher
MATCH (c:Customer)-[:PLACED]->(o:Order)<-[:SERVED]-(d:Driver)
WITH c.customer_id AS customer_id, d.driver_id AS driver_id, count(o) AS total_orders
WHERE total_orders >= 3
RETURN customer_id, driver_id, total_orders
ORDER BY total_orders DESC
LIMIT 20;
```

### 4.5. Tìm các customer dùng chung địa chỉ dropoff

```cypher
MATCH (c:Customer)-[:PLACED]->(o:Order)-[:DROPOFF_AT]->(a:Address)
WITH a, collect(DISTINCT c.customer_id) AS customers
WHERE size(customers) > 1
RETURN a.address, a.district, a.province, customers
LIMIT 20;
```

## 4.6. KB-C scope update for superfast driver-customer collusion

For the current ride-abuse scope, repeated customer-driver should be reviewed as a pair-level collusion problem instead of a simple repeat counter.

Recommended rule logic:

- group by `(driver_id, customer_id)`
- compute `n_trips`
- compute `n_ghost` where `avg_kmh = 0`
- keep only pairs with `n_trips > quantile(0.9999)` for the 4-day window, currently around `12` trips
- compute `min_gap_min` as the minimum minute gap between two consecutive trips of the same pair
- compute `ghost_rate = n_ghost / n_trips`
- mark `high_confidence = (ghost_rate > 0.3) OR (min_gap_min < 5)`

Columns that should be visible to analysts:

- `min_gap_min`
- `ghost_rate`
- `high_confidence`
- `avg_gmv`

Observed example:

- one pair reached `64` trips in 4 days
- average `gmv` was about `12,390 VND`
- the shortest gap between consecutive trips was `0.9` minutes, or about `54` seconds

Interpretation:

- very high pair frequency alone is suspicious
- zero-speed ride share and sub-5-minute turnaround sharply increase confidence of collusion or ghost-trip farming
- low average GMV can indicate subsidy capture rather than genuine transport demand

## 5. Demo Visualize Fraud Case

MATCH path1 =
    (c:Customer {customer_id: 'e1bccf5c09705f63'})
    -[:PLACED]->
    (o:Order)
    <-[:SERVED]-
    (d:Driver {driver_id: '4c8abb2a3a6ab995'})

OPTIONAL MATCH path2 = (o)-[:FROM_MERCHANT]->(m:Merchant)
OPTIONAL MATCH path3 = (o)-[:USED_PROMO]->(p:PromotionCode)
OPTIONAL MATCH path4 = (o)-[:PAID_BY]->(pm:PaymentMethod)
OPTIONAL MATCH path5 = (o)-[:PICKUP_AT]->(pickup:Address)
OPTIONAL MATCH path6 = (o)-[:DROPOFF_AT]->(dropoff:Address)

RETURN path1, path2, path3, path4, path5, path6
LIMIT 200;

MATCH path =
    (c:Customer {customer_id: 'e1bccf5c09705f63'})
    -[:PLACED]->
    (o:Order)
    <-[:SERVED]-
    (d:Driver {driver_id: '4c8abb2a3a6ab995'})

WHERE datetime(o.order_time) >= datetime('2026-07-13T00:00:00')
  AND datetime(o.order_time) < datetime('2026-07-14T00:00:00')

OPTIONAL MATCH merchantPath =
    (o)-[:FROM_MERCHANT]->(m:Merchant)

OPTIONAL MATCH promoPath =
    (o)-[:USED_PROMO]->(p:PromotionCode)

RETURN path, merchantPath, promoPath
LIMIT 100;
