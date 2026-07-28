# Sprint 1 Status Report

## Scope

Sprint 1 scope being reviewed:

1. Tìm hiểu domain Anti-Fraud và các dạng fraud hiện có
2. Khảo sát schema dữ liệu
3. Thiết kế graph schema (Node, Relationship, Property)
4. Viết pipeline chuyển dữ liệu từ SQL/CSV sang Graph DB (Neo4j hoặc tương đương)
5. Import dữ liệu mẫu và kiểm tra tính đúng đắn
6. Xây dựng một số query Cypher cơ bản để truy vấn quan hệ
7. Thử visualize một vài case fraud đã biết

Review date:

- Friday, July 24, 2026

## Overall Status

| Hạng mục | Trạng thái | Đánh giá ngắn |
|---|---|---|
| Domain Anti-Fraud research | `DONE` | Đã xác định được các tín hiệu fraud chính để đưa vào graph: promo abuse, repeated customer-driver, shared payment, shared address, merchant concentration, trip/fulfillment anomaly. |
| Data schema survey | `DONE` | Đã khảo sát cleaned-order schema cho cả `food` và `ride`, xác định các trường khóa, trường thời gian, trường định danh và shared signals cần đưa vào graph. |
| Graph schema design | `DONE` | Đã thiết kế schema gồm node, relationship, property và constraints cho Neo4j; có cả base graph và hướng mở rộng storytelling layer. |
| SQL/CSV -> Graph pipeline | `DONE` | Đã có pipeline đọc từ SQL/CSV/Parquet, chuẩn hóa dữ liệu, sinh file import Neo4j và manifest/quality report. |
| Sample import + correctness checks | `DONE` | Đã import được dữ liệu mẫu `food` và `ride`, sinh count/manifest, quality report và có test cho importer/pipeline. |
| Basic Cypher queries | `DONE` | Đã có các Cypher phục vụ rule detection, signal building, similarity grouping và truy vấn quan hệ cơ bản trong graph. |
| Visualization of known fraud cases | `PARTIAL` | Đã sẵn sàng visualize trên Neo4j Browser và đã materialize group/case trong graph, nhưng chưa có bộ known fraud labels chuẩn để minh họa các case đã xác minh end-to-end. |

## 1. Tìm Hiểu Domain Anti-Fraud Và Các Dạng Fraud

**Status:** `DONE`

Sprint 1 đã hình thành được understanding đủ sâu để thiết kế graph anti-fraud theo hướng điều tra quan hệ thay vì chỉ nhìn từng order độc lập.

Các dạng fraud/tín hiệu chính đã được phản ánh trong repo:

- promo abuse / promo concentration
- repeated customer-driver collusion
- shared payment method across many accounts
- shared pickup/dropoff address
- merchant-centric suspicious concentration
- ride/trip anomaly
- food fulfillment anomaly

Điều này cho thấy phần domain research không chỉ dừng ở mô tả nghiệp vụ mà đã được chuyển thành graph signal và rule/query cụ thể.

**Bằng chứng**

- [docs/task3_csv_to_neo4j_import.md](/D:/VSF/docs/task3_csv_to_neo4j_import.md)
- [docs/anti_fraud_minimum_graph_schema.md](/D:/VSF/docs/anti_fraud_minimum_graph_schema.md)
- [src/algorithms/graph_fraud_pipeline.py](/D:/VSF/src/algorithms/graph_fraud_pipeline.py:1)

## 2. Khảo Sát Schema Dữ Liệu

**Status:** `DONE`

Đã khảo sát schema dữ liệu đầu vào ở dạng cleaned orders cho hai domain:

- `food`: [data/handoff/food/cleaned_orders/orders_food_clean_dashboard.parquet](/D:/VSF/data/handoff/food/cleaned_orders/orders_food_clean_dashboard.parquet)
- `ride`: [data/handoff/ride/cleaned_orders/orders_ride_clean_2026-07-14_to_17.parquet](/D:/VSF/data/handoff/ride/cleaned_orders/orders_ride_clean_2026-07-14_to_17.parquet)

Các nhóm trường chính đã được xác định rõ:

- khóa định danh: `order_id`, `customer_id`, `driver_id`, `merchant_id`
- thời gian: `order_time_local_tz`, `complete_time_local_tz`
- shared signals: địa chỉ, payment method, promotion code, promotion campaign
- thuộc tính phục vụ điều tra: `status`, `discount`, `gmv`, `commission`, `net_income`
- thuộc tính domain-specific cho `ride` và `food`

Importer cũng đã encode trực tiếp hiểu biết này vào mapping đầu vào.

**Bằng chứng**

- [scripts/prepare_clean_orders_neo4j_import.py](/D:/VSF/scripts/prepare_clean_orders_neo4j_import.py:18)
- [docs/task3_csv_to_neo4j_import.md](/D:/VSF/docs/task3_csv_to_neo4j_import.md)
- [tests/test_prepare_clean_orders_neo4j_import.py](/D:/VSF/tests/test_prepare_clean_orders_neo4j_import.py)

## 3. Thiết Kế Graph Schema

**Status:** `DONE`

Đã có thiết kế graph schema tương đối đầy đủ cho Sprint 1.

### Node chính

- `Customer`
- `Order`
- `Driver`
- `Merchant`
- `Address`
- `PaymentMethod`
- `PromotionCode`
- `PromotionCampaign`

Ngoài ra repo cũng hỗ trợ các node taxonomy/phụ:

- `CancelActor`
- `CancelReason`
- `DropoffFailActor`
- `DropoffFailCode`
- `RideService`
- `ServiceType`
- `SubVertical`
- `TravelMode`
- `ChannelType`

### Relationship chính

- `PLACED`
- `SERVED`
- `FROM_MERCHANT`
- `PICKUP_AT`
- `DROPOFF_AT`
- `PAID_BY`
- `USED_PROMO`
- `IN_CAMPAIGN`

### Property chính trên `Order`

- định danh và domain
- trạng thái/cancel info
- timestamp nghiệp vụ
- chỉ số tiền: `gmv`, `discount`, `commission`, `net_income`
- chỉ số domain-specific như `lead_time_second`, `declared_km`, `actual_km`

Schema cũng đã có constraints/index cho Neo4j để đảm bảo uniqueness và hỗ trợ truy vấn.

**Bằng chứng**

- [docs/anti_fraud_minimum_graph_schema.md](/D:/VSF/docs/anti_fraud_minimum_graph_schema.md)
- [docs/storytelling_graph_schema_v2.md](/D:/VSF/docs/storytelling_graph_schema_v2.md)
- [src/graph/cypher/001_constraints.cypher](/D:/VSF/src/graph/cypher/001_constraints.cypher)

## 4. Pipeline Chuyển Dữ Liệu Từ SQL/CSV Sang Graph DB

**Status:** `DONE`

Đã có pipeline import thống nhất cho nhiều loại input:

- `SQL`
- `.csv`
- `.parquet`

Luồng xử lý hiện tại:

1. đọc dữ liệu từ file hoặc SQL source
2. chuẩn hóa cột và kiểu dữ liệu
3. quality checks cho khóa bắt buộc
4. entity resolution, đặc biệt là address normalization + hashing
5. sinh file `headers/`, `nodes/`, `relationships/`
6. tạo `manifest.json` và `quality_report.csv`
7. import vào Neo4j bằng `neo4j-admin import`

Điểm mạnh của Sprint 1 là pipeline không chỉ dừng ở proof-of-concept mà đã có hỗ trợ SQL source thực tế và có khả năng chạy cho cả `food` lẫn `ride`.

**Bằng chứng**

- [scripts/prepare_clean_orders_neo4j_import.py](/D:/VSF/scripts/prepare_clean_orders_neo4j_import.py)
- [docs/task3_csv_to_neo4j_import.md](/D:/VSF/docs/task3_csv_to_neo4j_import.md)
- [infra/docker-compose.yml](/D:/VSF/infra/docker-compose.yml)
- [tests/test_prepare_clean_orders_neo4j_import.py](/D:/VSF/tests/test_prepare_clean_orders_neo4j_import.py)

## 5. Import Dữ Liệu Mẫu Và Kiểm Tra Tính Đúng Đắn

**Status:** `DONE`

### Kết quả import mẫu `food`

Theo [data/neo4j-import/neo4j-import-food/manifest.json](/D:/VSF/data/neo4j-import/neo4j-import-food/manifest.json):

- `120,171` orders
- `84,030` customers
- `21,535` drivers
- `19,289` merchants
- `49,821` addresses
- `2,878` promotion codes

Quality report hiện tại cho `food`:

- `missing_order_id = 0`
- `missing_customer_id = 0`
- `missing_order_time_local_tz = 0`
- `duplicate_order_id = 0`

### Kết quả import mẫu `ride`

Theo [data/neo4j-import/neo4j-import-ride/manifest.json](/D:/VSF/data/neo4j-import/neo4j-import-ride/manifest.json):

- `6,083,536` orders
- `2,166,624` customers
- `209,394` drivers
- `1,036,054` addresses
- `178,063` promotion codes

Quality report hiện tại cho `ride`:

- `missing_order_id = 0`
- `missing_order_time_local_tz = 0`
- `duplicate_order_id = 0`
- `missing_customer_id = 279,132`

Như vậy, Sprint 1 đã hoàn thành phần kiểm tra đúng đắn ở mức kỹ thuật:

- có `quality_report.csv`
- có `manifest.json`
- có script verify graph count sau import
- có test unit cho normalize, address key, SQL read, batch source, quality check

Kết quả test đã chạy ngày Friday, July 24, 2026:

- `14 passed`

**Bằng chứng**

- [data/neo4j-import/neo4j-import-food/manifest.json](/D:/VSF/data/neo4j-import/neo4j-import-food/manifest.json)
- [data/neo4j-import/neo4j-import-ride/manifest.json](/D:/VSF/data/neo4j-import/neo4j-import-ride/manifest.json)
- [data/neo4j-import/neo4j-import-food/quality_report.csv](/D:/VSF/data/neo4j-import/neo4j-import-food/quality_report.csv)
- [data/neo4j-import/neo4j-import-ride/quality_report.csv](/D:/VSF/data/neo4j-import/neo4j-import-ride/quality_report.csv)
- [scripts/initialize_neo4j.py](/D:/VSF/scripts/initialize_neo4j.py)
- [tests/test_prepare_clean_orders_neo4j_import.py](/D:/VSF/tests/test_prepare_clean_orders_neo4j_import.py)
- [tests/test_graph_fraud_pipeline.py](/D:/VSF/tests/test_graph_fraud_pipeline.py)
- [tests/test_prepare_neo4j_import.py](/D:/VSF/tests/test_prepare_neo4j_import.py)

## 6. Một Số Query Cypher Cơ Bản Để Truy Vấn Quan Hệ

**Status:** `DONE`

Sprint 1 đã có các nhóm Cypher cơ bản phục vụ anti-fraud:

- truy vấn customer-order-driver
- truy vấn customer-order-address
- truy vấn order-promo-campaign
- truy vấn repeated customer-driver
- truy vấn promo-driver cluster
- truy vấn connected suspicious groups

Các query hiện diện dưới hai dạng:

- Cypher constraints/index trong `src/graph/cypher`
- Cypher nghiệp vụ được nhúng trong `GraphFraudPipeline`

Ví dụ các truy vấn/nghiệp vụ đã có:

- tính degree cho `Driver`, `Address`, `PromotionCode`
- build `USES_SIGNAL`
- detect repeated customer-driver pairs
- detect `PROMO_DRIVER_CLUSTER`
- project graph cho Node Similarity và WCC
- materialize `FraudGroup`

**Bằng chứng**

- [src/algorithms/graph_fraud_pipeline.py](/D:/VSF/src/algorithms/graph_fraud_pipeline.py)
- [src/graph/cypher/001_constraints.cypher](/D:/VSF/src/graph/cypher/001_constraints.cypher)

## 7. Visualize Một Vài Case Fraud Đã Biết

**Status:** `PARTIAL`

Sprint 1 đã đạt được nền tảng để visualize case trên Neo4j Browser:

- graph entities và relationships đã được import
- constraints/index đã sẵn sàng
- suspicious groups có thể được materialize thành `FraudGroup`
- Docker Compose đã dựng sẵn Neo4j với `APOC` và `GDS`

Tuy nhiên, phần này mới ở mức `PARTIAL` vì:

- chưa thấy bộ `known fraud labels` hoặc danh sách case đã xác minh trong repo
- chưa có file visualization guide/query tách riêng cho Sprint 1
- việc visualize hiện dựa trên graph groups và suspicious patterns hơn là “known confirmed fraud cases”

Nói cách khác, nền tảng visualization đã có, nhưng phần minh họa bằng case fraud đã biết vẫn cần upstream labels hoặc case list từ nghiệp vụ.

**Bằng chứng**

- [infra/docker-compose.yml](/D:/VSF/infra/docker-compose.yml)
- [src/algorithms/graph_fraud_pipeline.py](/D:/VSF/src/algorithms/graph_fraud_pipeline.py)
- [scripts/initialize_neo4j.py](/D:/VSF/scripts/initialize_neo4j.py)

## Kết Luận

Sprint 1 có thể đánh giá là:

- **đã hoàn thành phần khảo sát dữ liệu và thiết kế graph schema**
- **đã hoàn thành pipeline chuyển dữ liệu từ SQL/CSV/Parquet sang Neo4j**
- **đã import được dữ liệu mẫu và có kiểm tra đúng đắn bằng manifest, quality report và test**
- **đã có các Cypher cơ bản để truy vấn quan hệ và phát hiện pattern nghi vấn**
- **phần visualize known fraud cases mới hoàn thành một phần do chưa có ground-truth case list**

## Gợi Ý Chốt Sprint 1

1. bổ sung một tài liệu riêng về taxonomy fraud theo domain để phần domain research rõ hơn với mentor/business
2. chốt một bộ query demo tách riêng thành file `.cypher` để thuận tiện demo
3. xin upstream một danh sách known fraud cases hoặc confirmed labels để validate và visualize thực chiến
4. nếu chạy chung `food` và `ride`, nên sớm chuyển khóa `Order` sang `domain + order_id` như khuyến nghị trong schema note
