# Note Ve Property Va Relationship Cho Dữ Liệu `ride` / `food`

## Phạm vi tài liệu

Tai liệu này giải thích vai trò của `property` và `relationship` trong order graph hiện có, nhưng được viết lại để phù hợp với hướng mới của project:

- `docs/graph_algorithms_for_driver_customer_ghost_trip_collusion.md`

Mục tiêu là làm rõ:

- dữ liệu nào là `graph core input`
- dữ liệu nào là `shared-entity support`
- dữ liệu nào là `optional enrichment`

## Kết luận nhanh

Trong hướng mới, schema order graph nên được hiểu theo 3 lớp:

1. `pair graph inputs`
2. `suspicious graph inputs`
3. `enrichment attributes`

Nói cách khác:

- không phải mọi property/relationship đều có vai trò ngang nhau
- ưu tiên cao nhất là các thành phần giúp aggregate thành pair `driver-customer`
- ưu tiên kế tiếp là các thành phần giúp nối suspicious pairs để chạy `WCC`

## 1. Pair graph inputs

Đây là những thành phần quan trọng nhất nếu project đi theo 3 graph algorithms cốt lõi.

Cần có:

- node `Order`
- node `Driver`
- node `Customer`
- `(:Customer)-[:PLACED]->(:Order)`
- `(:Driver)-[:SERVED]->(:Order)`

Từ những liên kết này downstream mới có thể tổng hợp thành:

- `trip_count`
- `driver_trip_count`
- `customer_trip_count`
- `pair_share_driver`
- `pair_share_customer`

Nếu thiếu lớp này, không thể build đúng `weighted edge outlier detection` và `bipartite concentration scoring`.

## 2. Suspicious graph inputs

Đây là lớp dữ liệu dùng để nối suspicious pairs thành network phục vụ `WCC`.

Quan trọng nhất:

- `Address`
- `PaymentMethod`
- `PromotionCode`
- `PromotionCampaign`

Quan hệ liên quan:

- `PICKUP_AT`
- `DROPOFF_AT`
- `PAID_BY`
- `USED_PROMO`
- `IN_CAMPAIGN`

Vai trò:

- nối pair qua shared address
- nối pair qua shared payment
- nối pair qua shared promo

Đây là phần schema phục vụ trực tiếp cho suspicious graph, khác với pair graph core nhưng vẫn là mandatory support cho giai đoạn cluster investigation.

## 3. Enrichment attributes

Nhóm này vẫn hữu ích, nhưng không phải trung tâm của hướng mới.

Ví dụ:

- `avg_kmh`
- `declared_km`
- `actual_km`
- `km_diff`
- `intrip_time_second`
- `lead_time_second`
- `gmv`
- `discount`
- `service_name`
- `service_type`
- `sub_vertical_name`
- `travel_mode`
- `channel_type`

Chung có thể được dùng để:

- tạo business filters
- giải thích case
- tính enrichment signals sau này

Nhưng không nên làm lu mờ 2 lớp ưu tiên cao hơn.

## 4. Cách hiểu đúng mô hình lai property + relationship

Schema hiện có có nhiều nhóm dữ liệu vừa tồn tại dưới dạng `property` trên `Order`, vừa tồn tại dưới dạng node/relationship chuẩn hóa.

Điều này vẫn hợp lý trong hướng mới vì:

- property giúp filter nhanh và làm feature table
- relationship giúp graph traversal và shared-entity linking

Do đó, không cần ép buộc schema về một cực:

- "chỉ property"
- hoặc "chỉ relationship"

Cần đánh giá mọi trường theo câu hỏi:

- có phục vụ pair graph không?
- có phục vụ suspicious graph không?
- hay chỉ là enrichment?

## 5. Các thành phần quan trọng nhất đối với hướng `Driver-Customer Ghost-Trip Collusion`

Nếu phải ưu tiên schema theo tác động tới hướng mới, thứ tự nên là:

1. `Driver`, `Customer`, `Order`
2. `PLACED`, `SERVED`
3. `Address`, `PaymentMethod`, `PromotionCode`
4. `PICKUP_AT`, `DROPOFF_AT`, `PAID_BY`, `USED_PROMO`
5. metric và taxonomy enrichment

Đây là cách nhìn schema phù hợp nhất với pipeline:

1. build pair table
2. score suspicious pairs
3. build suspicious graph
4. run `WCC`

## 6. Food và ride nên được đọc thế nào trong bối cảnh này

`ride` là domain ưu tiên cho hướng mới, vì bài toán hiện tại là `Driver-Customer Ghost-Trip Collusion`.

Do đó:

- các liên kết giữa `Driver`, `Customer`, `Order` là trọng tâm
- shared entities phục vụ repeated pair investigation là trọng tâm

`food` vẫn có giá trị ở mức schema dùng chung, nhưng không nên chi phối cách mô tả ưu tiên modeling cho bài toán này.

## 7. Final note

Khi doc schema hiện có để phục vụ hướng mới, nên nhớ:

- `Order` graph là tầng lưu trữ và truy vết
- `pair graph` mới là tầng phân tích cốt lõi
- `suspicious graph` là tầng điều tra network

Vì vậy, doc/schema note này nên được hiểu như một tài liệu định hướng ưu tiên dữ liệu cho bài toán pair-collusion, không phải một bản inventory trùng lặp mới field trong importer.
