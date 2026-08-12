# Sprint 2 Scope: KB-C Driver-Customer Ghost-Trip Collusion

## Problem statement

Sprint 2 được reset scope để đi đúng một pattern gian lận cụ thể:

- driver và customer thông đồng tạo ghost trips
- cùng một pair lặp lại với tần suất bất thường
- hành vi nghi ngờ được nhìn trước hết ở cấp `driver-customer pair`

 Tài liệu này theo sát hướng:

- `docs/graph_algorithms_for_driver_customer_ghost_trip_collusion.md`

## Sprint 2 objective

Mục tiêu của Sprint 2 không phải build một fraud engine đầy đủ ngay lập tức.

Mục tiêu đúng hơn là xây được `graph core MVP` cho bài toán:

1. shortlist suspicious pairs
2. score mức độ collusion của pair
3. gom pair thanh suspicious components de review

## Graph abstraction chốt

Đơn vị graph trung tâm:

- node `Driver`
- node `Customer`
- weighted edge giữa `Driver` và `Customer`

Trên mỗi edge cần có tối thiểu:

- `trip_count`
- `driver_trip_count`
- `customer_trip_count`
- `pair_share_driver`
- `pair_share_customer`

Đây là abstraction đủ để chạy MVP mà không phụ thuộc vào nhiều feature phụ.

## Algorithms trong scope Sprint 2

Sprint 2 chỉ nên chốt 3 graph algorithms cốt lõi:

1. `Weighted edge outlier detection`
2. `Bipartite concentration scoring`
3. `WCC`

## 1. Weighted edge outlier detection

Dùng để:

- tìm pair có `trip_count` nằm ở tail của phân phối

Đây là first-pass detector và là nguồn tạo suspicious seeds.

## 2. Bipartite concentration scoring

Dùng để:

- đo xem pair có chiếm một tỷ trọng bất thường trên cả phía driver và customer hay không

Đây là lớp refinement quan trọng nhất để xác định collusion thay vì chỉ nhìn volume thuần túy.

## 3. WCC

Dùng để:

- gom suspicious pairs thành component trên suspicious graph

Suspicious graph được nối bằng các shared entities hữu ích cho điều tra, ví dụ:

- shared address
- shared payment
- shared promo
- shared driver
- shared customer

## Ngoài scope Sprint 2 core

Các ý tưởng sau có thể làm sau, nhưng không nên là blocker của Sprint 2:

- temporal anomaly scoring
- ghost-rate scoring
- route-loop scoring
- Louvain
- k-core
- node similarity tổng quát

Lý do:

- không cần để chốt MVP graph core
- để tạo scope quá rộng
- để làm mờ bài toán repeated pair collusion

## Deliverables nên có ở cuối Sprint 2

Sprint 2 nên kết thúc với các đầu ra sau:

1. `pair table` theo time window
2. `volume_score` cho mỗi pair
3. `concentration_score` cho mỗi pair
4. `suspicious_pair_list`
5. `suspicious_graph`
6. `component_id` và `component_size`
7. `flagged_orders` để analyst review

## Proposed build order

Thứ tự triển khai để tránh scope creep:

1. Build pair stats
2. Run weighted edge outlier detection
3. Run bipartite concentration scoring
4. Define suspicious pair criteria
5. Build suspicious graph
6. Run WCC
7. Materialize pair/component evidence xuống order level

## Role của operational signals

`ghost_rate`, `min_gap_min`, và `route reuse` vẫn phù hợp với bài toán ghost-trip, nhưng trong Sprint 2 chúng nên được xếp là:

- enrichment signals
- tie-breaker signals
- explainability signals

Không nên dùng chung để định nghĩa graph scope chính.

## Success criteria

Sprint 2 được xem là đạt hướng đúng nếu:

- pair-level detection trở thành trung tâm pipeline
- 3 graph algorithms cốt lõi đã được định nghĩa rõ
- suspicious components có thể được xuất ra để mở case điều tra
- các signal ngoài core được đặt đúng vị trí là enrichment

## Final note

Nếu cần giảm scope để đảm bảo tiến độ, thứ tự ưu tiên tuyệt đối trong Sprint 2 là:

1. `Weighted edge outlier detection`
2. `Bipartite concentration scoring`
3. `WCC`

